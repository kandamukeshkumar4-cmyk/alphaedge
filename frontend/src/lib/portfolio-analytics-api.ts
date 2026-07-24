/**
 * Loop V92 (PU1) — portfolio analytics typed client.
 *
 * Backend contract (frozen, V92 P3):
 *   GET /api/v1/portfolio/analytics?days=30
 *   -> {
 *        pnl_series: [{date, realized_pnl, unrealized_pnl, equity}],
 *        summary: {
 *          total_realized, total_unrealized, win_rate, trades_closed,
 *          trades_open, best_trade, worst_trade, avg_hold_hours
 *        },
 *        calibration: {
 *          buckets: [{predicted_prob_bucket, actual_rate, n}],
 *          paper_trading_only: true
 *        }
 *      }
 *
 * Live-first with a mandatory in-memory PAPER mock fallback (same pattern as
 * terminal-api.ts / notifications-api.ts). Never rejects — the Analytics UI
 * stays verifiable while the backend lands in parallel. Paper trading only;
 * no order path.
 */

import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

export type AnalyticsDays = 7 | 30 | 90;

export const ANALYTICS_DAY_OPTIONS: readonly AnalyticsDays[] = [7, 30, 90];

export type PnLSeriesPoint = {
  date: string;
  realized_pnl: number;
  unrealized_pnl: number;
  equity: number;
};

export type PortfolioAnalyticsSummary = {
  total_realized: number;
  total_unrealized: number;
  win_rate: number;
  trades_closed: number;
  trades_open: number;
  best_trade: number;
  worst_trade: number;
  avg_hold_hours: number;
};

export type PortfolioCalibrationBucket = {
  predicted_prob_bucket: string;
  actual_rate: number;
  n: number;
};

export type PortfolioCalibration = {
  buckets: PortfolioCalibrationBucket[];
  paper_trading_only: boolean;
};

export type PortfolioAnalytics = {
  pnl_series: PnLSeriesPoint[];
  summary: PortfolioAnalyticsSummary;
  calibration: PortfolioCalibration;
};

export type AnalyticsApiSource = "live" | "mock";

export type PortfolioAnalyticsResult = {
  data: PortfolioAnalytics;
  source: AnalyticsApiSource;
};

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type FetchAnalyticsOptions = {
  days?: AnalyticsDays | number;
  token?: string | null;
  apiBase?: string;
  fetcher?: Fetcher;
  signal?: AbortSignal;
};

const EMPTY_SUMMARY: PortfolioAnalyticsSummary = {
  total_realized: 0,
  total_unrealized: 0,
  win_rate: 0,
  trades_closed: 0,
  trades_open: 0,
  best_trade: 0,
  worst_trade: 0,
  avg_hold_hours: 0,
};

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asFinite(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/** Clamp to the UI day options; backend accepts 1–365, we only offer 7/30/90. */
export function normalizeAnalyticsDays(raw: unknown): AnalyticsDays {
  const n = typeof raw === "number" ? raw : Number(raw);
  if (n === 7 || n === 90) return n;
  return 30;
}

export function normalizePnLSeriesPoint(raw: unknown): PnLSeriesPoint | null {
  const rec = asRecord(raw);
  if (typeof rec.date !== "string" || rec.date === "") return null;
  return {
    date: rec.date,
    realized_pnl: asFinite(rec.realized_pnl),
    unrealized_pnl: asFinite(rec.unrealized_pnl),
    equity: asFinite(rec.equity),
  };
}

export function normalizeCalibrationBucket(
  raw: unknown,
): PortfolioCalibrationBucket | null {
  const rec = asRecord(raw);
  if (typeof rec.predicted_prob_bucket !== "string" || rec.predicted_prob_bucket === "") {
    return null;
  }
  return {
    predicted_prob_bucket: rec.predicted_prob_bucket,
    actual_rate: asFinite(rec.actual_rate),
    n: Math.max(0, Math.round(asFinite(rec.n))),
  };
}

/** Tolerant normalizer — backend sends dicts; never throw on drift. */
export function normalizePortfolioAnalytics(raw: unknown): PortfolioAnalytics {
  const rec = asRecord(raw);
  const summaryRec = asRecord(rec.summary);
  const calibRec = asRecord(rec.calibration);
  const series = Array.isArray(rec.pnl_series)
    ? rec.pnl_series
        .map(normalizePnLSeriesPoint)
        .filter((p): p is PnLSeriesPoint => p !== null)
    : [];
  const buckets = Array.isArray(calibRec.buckets)
    ? calibRec.buckets
        .map(normalizeCalibrationBucket)
        .filter((b): b is PortfolioCalibrationBucket => b !== null)
    : [];
  return {
    pnl_series: series,
    summary: {
      total_realized: asFinite(summaryRec.total_realized),
      total_unrealized: asFinite(summaryRec.total_unrealized),
      win_rate: asFinite(summaryRec.win_rate),
      trades_closed: Math.max(0, Math.round(asFinite(summaryRec.trades_closed))),
      trades_open: Math.max(0, Math.round(asFinite(summaryRec.trades_open))),
      best_trade: asFinite(summaryRec.best_trade),
      worst_trade: asFinite(summaryRec.worst_trade),
      avg_hold_hours: asFinite(summaryRec.avg_hold_hours),
    },
    calibration: {
      buckets,
      paper_trading_only: calibRec.paper_trading_only !== false,
    },
  };
}

/** True when the book has no closed/open trades and no equity trail. */
export function isEmptyPortfolioAnalytics(data: PortfolioAnalytics): boolean {
  return (
    data.pnl_series.length === 0 &&
    data.summary.trades_closed === 0 &&
    data.summary.trades_open === 0 &&
    data.summary.total_realized === 0 &&
    data.summary.total_unrealized === 0
  );
}

// ---------------------------------------------------------------------------
// PAPER mock (seeded Lakers/Celtics desk — clearly shaped, not fabricated edge)
// ---------------------------------------------------------------------------

function isoDay(offsetFromEnd: number, days: number): string {
  const end = Date.UTC(2026, 6, 24); // 2026-07-24
  const t = end - (days - 1 - offsetFromEnd) * 86_400_000;
  return new Date(t).toISOString().slice(0, 10);
}

function buildMockSeries(days: AnalyticsDays): PnLSeriesPoint[] {
  const startEquity = 100_000;
  return Array.from({ length: days }, (_, i) => {
    const realized = +(i * 2.4).toFixed(2);
    const unrealized = +(8 + Math.sin(i / 3) * 6).toFixed(2);
    return {
      date: isoDay(i, days),
      realized_pnl: realized,
      unrealized_pnl: unrealized,
      equity: +(startEquity + realized + unrealized).toFixed(2),
    };
  });
}

function buildMockAnalytics(days: AnalyticsDays): PortfolioAnalytics {
  const pnl_series = buildMockSeries(days);
  return {
    pnl_series,
    summary: {
      total_realized: pnl_series.at(-1)?.realized_pnl ?? 0,
      total_unrealized: pnl_series.at(-1)?.unrealized_pnl ?? 0,
      win_rate: 0.62,
      trades_closed: 8,
      trades_open: 2,
      best_trade: 18.5,
      worst_trade: -9.2,
      avg_hold_hours: 36.5,
    },
    calibration: {
      buckets: [
        { predicted_prob_bucket: "0.3-0.4", actual_rate: 0.33, n: 3 },
        { predicted_prob_bucket: "0.4-0.5", actual_rate: 0.5, n: 4 },
        { predicted_prob_bucket: "0.5-0.6", actual_rate: 0.55, n: 5 },
        { predicted_prob_bucket: "0.6-0.7", actual_rate: 0.67, n: 3 },
      ],
      paper_trading_only: true,
    },
  };
}

/** Empty mock used only when explicitly requested by tests. */
export function emptyPortfolioAnalytics(): PortfolioAnalytics {
  return {
    pnl_series: [],
    summary: { ...EMPTY_SUMMARY },
    calibration: { buckets: [], paper_trading_only: true },
  };
}

export function getMockPortfolioAnalytics(
  days: AnalyticsDays | number = 30,
): PortfolioAnalytics {
  return buildMockAnalytics(normalizeAnalyticsDays(days));
}

// ---------------------------------------------------------------------------
// Fetch layer
// ---------------------------------------------------------------------------

async function resolveBase(apiBase?: string): Promise<string> {
  if (typeof apiBase === "string") return apiBase.trim().replace(/\/+$/, "");
  return (await ensureApiBase()) || API_BASE;
}

/**
 * Fetch portfolio analytics. Live GET first; on any failure (no base, network,
 * non-OK, bad JSON) returns the seeded PAPER mock. Never rejects.
 */
export async function fetchPortfolioAnalytics(
  input: FetchAnalyticsOptions = {},
): Promise<PortfolioAnalyticsResult> {
  const days = normalizeAnalyticsDays(input.days ?? 30);
  const path = `/api/v1/portfolio/analytics?days=${days}`;
  const base = await resolveBase(input.apiBase);

  if (hasLiveApi(base) || input.fetcher) {
    try {
      const fetcher = input.fetcher ?? fetch;
      const response = await fetcher(apiUrl(path, base), {
        cache: "no-store",
        signal: input.signal,
        headers: {
          Accept: "application/json",
          ...(input.token ? { Authorization: `Bearer ${input.token}` } : {}),
        },
      });
      if (response.ok) {
        const body = (await response.json()) as unknown;
        return { data: normalizePortfolioAnalytics(body), source: "live" };
      }
    } catch {
      // fall through to mock
    }
  }

  return { data: getMockPortfolioAnalytics(days), source: "mock" };
}
