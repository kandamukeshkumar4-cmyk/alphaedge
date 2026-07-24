/**
 * Loop 99 AU1 — Technical-analysis indicators typed client.
 *
 * Backend contract (loop93 indicators router,
 * `backend/app/api/v1/indicators.py` + `app/services/technical_analysis_service.py`):
 *   GET /api/v1/markets/{slug}/indicators?window=90 ->
 *     {slug, points: [{t, close}],
 *      indicators: {rsi_14, macd: {macd, signal, hist}, sma_20, sma_50,
 *                   ema_12, bollinger: {upper, mid, lower}, adx_14},
 *      regime: "trending_up" | "trending_down" | "range" | "insufficient_data",
 *      paper_trading_only}
 *   Every indicator value may be null when the series is too short.
 *
 * Live first; on any failure the caller gets a deterministic PAPER mock
 * (the same seeded candle walk the price chart uses) with indicators
 * recomputed locally so the panel stays internally consistent offline.
 * All fetch wiring lives here — UI components never call `fetch` themselves.
 *
 * PAPER_TRADING_ONLY — descriptive TA on outcome-price series; no order path.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

export const INDICATORS_DEFAULT_WINDOW = 90;
export const INDICATORS_MIN_WINDOW = 20;
export const INDICATORS_MAX_WINDOW = 365;

// ---------------------------------------------------------------------------
// Types (backend contract)
// ---------------------------------------------------------------------------

export type IndicatorPoint = { t: number; close: number };

export type MacdValues = {
  macd: number | null;
  signal: number | null;
  hist: number | null;
};

export type BollingerValues = {
  upper: number | null;
  mid: number | null;
  lower: number | null;
};

export type IndicatorSet = {
  rsi_14: number | null;
  macd: MacdValues;
  sma_20: number | null;
  sma_50: number | null;
  ema_12: number | null;
  bollinger: BollingerValues;
  adx_14: number | null;
};

export type Regime =
  | "trending_up"
  | "trending_down"
  | "range"
  | "insufficient_data";

export type MarketIndicators = {
  slug: string;
  points: IndicatorPoint[];
  indicators: IndicatorSet;
  regime: Regime;
  paper_trading_only: boolean;
};

export type ApiSource = "live" | "mock";

export const REGIMES: readonly Regime[] = [
  "trending_up",
  "trending_down",
  "range",
  "insufficient_data",
];

/** Human label for a regime code. */
export function regimeLabel(regime: Regime): string {
  switch (regime) {
    case "trending_up":
      return "Trending up";
    case "trending_down":
      return "Trending down";
    case "range":
      return "Range-bound";
    case "insufficient_data":
      return "Insufficient data";
  }
}

// ---------------------------------------------------------------------------
// Normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asFiniteNumber(value: unknown): number | null {
  const n =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : NaN;
  return Number.isFinite(n) ? n : null;
}

const EMPTY_INDICATORS: IndicatorSet = {
  rsi_14: null,
  macd: { macd: null, signal: null, hist: null },
  sma_20: null,
  sma_50: null,
  ema_12: null,
  bollinger: { upper: null, mid: null, lower: null },
  adx_14: null,
};

function normalizeMacd(raw: unknown): MacdValues {
  const rec = asRecord(raw);
  return {
    macd: asFiniteNumber(rec.macd),
    signal: asFiniteNumber(rec.signal),
    hist: asFiniteNumber(rec.hist),
  };
}

function normalizeBollinger(raw: unknown): BollingerValues {
  const rec = asRecord(raw);
  return {
    upper: asFiniteNumber(rec.upper),
    mid: asFiniteNumber(rec.mid),
    lower: asFiniteNumber(rec.lower),
  };
}

function normalizeIndicatorSet(raw: unknown): IndicatorSet {
  const rec = asRecord(raw);
  if (Object.keys(rec).length === 0) return structuredClone(EMPTY_INDICATORS);
  return {
    rsi_14: asFiniteNumber(rec.rsi_14),
    macd: normalizeMacd(rec.macd),
    sma_20: asFiniteNumber(rec.sma_20),
    sma_50: asFiniteNumber(rec.sma_50),
    ema_12: asFiniteNumber(rec.ema_12),
    bollinger: normalizeBollinger(rec.bollinger),
    adx_14: asFiniteNumber(rec.adx_14),
  };
}

function normalizePoint(raw: unknown): IndicatorPoint | null {
  const rec = asRecord(raw);
  const t = asFiniteNumber(rec.t) ?? asFiniteNumber(rec.time);
  const close = asFiniteNumber(rec.close) ?? asFiniteNumber(rec.value);
  if (t === null || close === null) return null;
  return { t, close };
}

function normalizeIndicators(raw: unknown, slug: string): MarketIndicators | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.points)) return null;
  const points = rec.points
    .map(normalizePoint)
    .filter((p): p is IndicatorPoint => p !== null);
  points.sort((a, b) => a.t - b.t);
  const regime = REGIMES.includes(rec.regime as Regime)
    ? (rec.regime as Regime)
    : "insufficient_data";
  return {
    slug: typeof rec.slug === "string" && rec.slug ? rec.slug : slug,
    points,
    indicators: normalizeIndicatorSet(rec.indicators),
    regime,
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

// ---------------------------------------------------------------------------
// Pure indicator math (used by the mock fallback; mirrors the backend TA
// service closely enough that offline renders stay internally consistent)
// ---------------------------------------------------------------------------

export function sma(values: number[], period: number): number | null {
  if (values.length < period) return null;
  const slice = values.slice(-period);
  return slice.reduce((acc, v) => acc + v, 0) / period;
}

export function emaSeries(values: number[], period: number): number[] {
  if (values.length < period) return [];
  const alpha = 2 / (period + 1);
  let current = values.slice(0, period).reduce((acc, v) => acc + v, 0) / period;
  const out = [current];
  for (const value of values.slice(period)) {
    current += alpha * (value - current);
    out.push(current);
  }
  return out;
}

export function lastEma(values: number[], period: number): number | null {
  const series = emaSeries(values, period);
  return series.length > 0 ? series[series.length - 1] : null;
}

export function rsi14(values: number[], period = 14): number | null {
  if (values.length < period + 1) return null;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = values[i]! - values[i - 1]!;
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i]! - values[i - 1]!;
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
  }
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

export function macdLatest(values: number[]): MacdValues {
  const fast = emaSeries(values, 12);
  const slow = emaSeries(values, 26);
  if (fast.length === 0 || slow.length === 0) {
    return { macd: null, signal: null, hist: null };
  }
  // Align: slow starts at index 25, fast at index 11 → trim fast's head.
  const offset = fast.length - slow.length;
  const macdSeries = slow.map((v, i) => fast[i + offset]! - v);
  const signalSeries = emaSeries(macdSeries, 9);
  if (signalSeries.length === 0) {
    const macd = macdSeries[macdSeries.length - 1] ?? null;
    return { macd, signal: null, hist: null };
  }
  const macd = macdSeries[macdSeries.length - 1]!;
  const signal = signalSeries[signalSeries.length - 1]!;
  return { macd, signal, hist: macd - signal };
}

export function bollingerLatest(values: number[], period = 20, k = 2): BollingerValues {
  const mid = sma(values, period);
  if (mid === null) return { upper: null, mid: null, lower: null };
  const slice = values.slice(-period);
  const variance = slice.reduce((acc, v) => acc + (v - mid) ** 2, 0) / period;
  const band = k * Math.sqrt(variance);
  return { upper: mid + band, mid, lower: mid - band };
}

/**
 * Wilder ADX-14 over close-derived bars. `highs`/`lows` default to the close
 * series (mirrors the backend, which derives missing extremes from close).
 */
export function adx14(
  closes: number[],
  highs: number[] = closes,
  lows: number[] = closes,
  period = 14,
): number | null {
  if (closes.length < period * 2 + 1 || highs.length !== closes.length || lows.length !== closes.length) {
    return null;
  }
  const tr: number[] = [];
  const plusDm: number[] = [];
  const minusDm: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    const high = highs[i]!;
    const low = lows[i]!;
    const prevClose = closes[i - 1]!;
    const upMove = high - highs[i - 1]!;
    const downMove = lows[i - 1]! - low;
    tr.push(Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose)));
    plusDm.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDm.push(downMove > upMove && downMove > 0 ? downMove : 0);
  }
  // Wilder smoothing: seed with the sum of the first `period`, then decay.
  let trS = tr.slice(0, period).reduce((a, v) => a + v, 0);
  let pS = plusDm.slice(0, period).reduce((a, v) => a + v, 0);
  let mS = minusDm.slice(0, period).reduce((a, v) => a + v, 0);
  const dx: number[] = [];
  for (let i = period; i < tr.length; i++) {
    trS = trS - trS / period + tr[i]!;
    pS = pS - pS / period + plusDm[i]!;
    mS = mS - mS / period + minusDm[i]!;
    const plusDi = trS === 0 ? 0 : (100 * pS) / trS;
    const minusDi = trS === 0 ? 0 : (100 * mS) / trS;
    const diSum = plusDi + minusDi;
    dx.push(diSum === 0 ? 0 : (100 * Math.abs(plusDi - minusDi)) / diSum);
  }
  if (dx.length < period) return null;
  let adx = dx.slice(0, period).reduce((a, v) => a + v, 0) / period;
  for (const v of dx.slice(period)) {
    adx = (adx * (period - 1) + v) / period;
  }
  return adx;
}

export function computeIndicatorSet(closes: number[]): IndicatorSet {
  const macd = macdLatest(closes);
  const sma20 = sma(closes, 20);
  const sma50 = sma(closes, 50);
  const adx = adx14(closes);
  return {
    rsi_14: rsi14(closes),
    macd,
    sma_20: sma20,
    sma_50: sma50,
    ema_12: lastEma(closes, 12),
    bollinger: bollingerLatest(closes),
    adx_14: adx,
  };
}

/** Mirror of the backend `classify_regime` (public trend label). */
export function classifyRegime(indicators: IndicatorSet): Regime {
  const { sma_20, sma_50, adx_14 } = indicators;
  if (sma_20 === null || sma_50 === null || adx_14 === null) {
    return "insufficient_data";
  }
  if (adx_14 <= 20) return "range";
  if (sma_20 > sma_50) return "trending_up";
  if (sma_20 < sma_50) return "trending_down";
  return "range";
}

// ---------------------------------------------------------------------------
// Mock store (deterministic seeded walk — no Math.random / Date.now)
// ---------------------------------------------------------------------------

const MOCK_BASE_T = Date.parse("2026-07-20T00:00:00Z") / 1000;

function clamp01(v: number): number {
  return Math.min(0.98, Math.max(0.02, v));
}

/** Deterministic outcome-price walk: gentle uptrend + two bounded waves. */
export function mockIndicatorPoints(count = INDICATORS_DEFAULT_WINDOW): IndicatorPoint[] {
  const points: IndicatorPoint[] = [];
  for (let i = 0; i < count; i++) {
    const close = clamp01(
      0.46 +
        i * 0.0009 +
        Math.sin(i / 5.5) * 0.021 +
        Math.sin(i / 17) * 0.014,
    );
    points.push({ t: MOCK_BASE_T + i * 3600, close: Number(close.toFixed(4)) });
  }
  return points;
}

function buildMockIndicators(slug: string): MarketIndicators {
  const points = mockIndicatorPoints();
  const closes = points.map((p) => p.close);
  const indicators = computeIndicatorSet(closes);
  return {
    slug,
    points,
    indicators,
    regime: classifyRegime(indicators),
    paper_trading_only: true,
  };
}

/** Canonical seeded payload — exported for fixtures and offline fallback. */
export const MOCK_MARKET_INDICATORS: MarketIndicators = buildMockIndicators(
  "nba-2025-01-15-lal-bos",
);

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the indicators API)
// ---------------------------------------------------------------------------

type IndicatorsFetch = typeof fetch;

let indicatorsFetch: IndicatorsFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setIndicatorsFetch(fn: IndicatorsFetch): void {
  indicatorsFetch = fn;
}

/** Restore the default fetch layer (test hygiene). */
export function resetIndicatorsFetch(): void {
  indicatorsFetch = (...args) => fetch(...args);
}

async function tryLiveJson<T>(
  path: string,
  token: string | null,
): Promise<T | null> {
  const base = (await ensureApiBase()) || undefined;
  if (!base || !hasLiveApi(base)) return null;
  try {
    const res = await indicatorsFetch(apiUrl(path, base), {
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Technical analysis over a market's outcome-price candles.
 * Live first; deterministic paper mock fallback. Never rejects.
 */
export async function fetchMarketIndicators(
  slug: string,
  options: {
    window?: number;
    token?: string | null;
  } = {},
): Promise<{ data: MarketIndicators; source: ApiSource }> {
  const window = Math.min(
    INDICATORS_MAX_WINDOW,
    Math.max(INDICATORS_MIN_WINDOW, Math.round(options.window ?? INDICATORS_DEFAULT_WINDOW)),
  );
  const live = await tryLiveJson<unknown>(
    `/api/v1/markets/${encodeURIComponent(slug)}/indicators?window=${window}`,
    options.token ?? null,
  );
  const normalized = live ? normalizeIndicators(live, slug) : null;
  if (normalized) return { data: normalized, source: "live" };
  return { data: buildMockIndicators(slug), source: "mock" };
}
