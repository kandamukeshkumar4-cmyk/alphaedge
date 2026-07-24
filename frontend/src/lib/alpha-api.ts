/**
 * Loop 99 AU1 — Multi-Factor Alpha typed client.
 *
 * Backend contract (loop96 alpha router, `backend/app/api/v1/alpha.py` +
 * `app/alpha/alpha_service.py`):
 *   GET /api/v1/alpha/factors?market=<slug> ->
 *     {market, as_of, factors: [{name, score, valid, t_stat, reason,
 *      provenance: {available, reason?, fields?}}],
 *      rejected_factors: [{name, reason}], paper_trading_only}
 *   GET /api/v1/alpha/report ->
 *     {factors: [{name, valid, reason, count, t_stat, is_brier?, oos_brier?,
 *      closing_brier?, brier_delta_vs_closing?, bootstrap_lower?,
 *      oos_degradation?, oos_count?, correlation_clusters?,
 *      missing_factor_provenance?, missing_closing_line?}],
 *      valid_factor_count, rejected_factors, paper_trading_only}
 *
 * The live API is attempted first; on any failure the caller gets an
 * in-memory PAPER mock so the /alpha research view works while the backend
 * is absent. All fetch wiring lives in this one file — UI components never
 * call `fetch` themselves.
 *
 * PAPER_TRADING_ONLY — research signals only; nothing here constructs orders.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/** Canonical paper market shared with the research terminal. */
export const ALPHA_CANONICAL_MARKET = "nba-2025-01-15-lal-bos";

// ---------------------------------------------------------------------------
// Types (backend contract)
// ---------------------------------------------------------------------------

export type AlphaFactorProvenance = {
  available: boolean;
  reason: string | null;
  fields: string[];
};

export type AlphaFactor = {
  name: string;
  /** Research score in [-1, 1]. */
  score: number;
  /** True only when the factor is available AND survived OOS validation. */
  valid: boolean;
  /** Newey-West t-stat from the independent validator; null when unknown. */
  t_stat: number | null;
  /** Kill reason when invalid; null when the factor survived. */
  reason: string | null;
  provenance: AlphaFactorProvenance;
};

export type AlphaRejection = { name: string; reason: string | null };

export type AlphaFactors = {
  market: string;
  as_of: string | null;
  factors: AlphaFactor[];
  rejected_factors: AlphaRejection[];
  paper_trading_only: boolean;
};

export type AlphaReportFactor = {
  name: string;
  valid: boolean;
  reason: string | null;
  count: number;
  t_stat: number | null;
  is_brier: number | null;
  oos_brier: number | null;
  closing_brier: number | null;
  brier_delta_vs_closing: number | null;
  bootstrap_lower: number | null;
  oos_degradation: number | null;
  oos_count: number | null;
  correlation_clusters: number | null;
};

export type AlphaReport = {
  factors: AlphaReportFactor[];
  valid_factor_count: number;
  rejected_factors: AlphaRejection[];
  paper_trading_only: boolean;
};

export type ApiSource = "live" | "mock";

// ---------------------------------------------------------------------------
// Human-readable kill reasons (validator rejection codes → UI copy)
// ---------------------------------------------------------------------------

const REJECTION_LABELS: Record<string, string> = {
  oos_does_not_beat_closing: "Did not beat the closing line out-of-sample",
  bootstrap_ci_not_positive: "Bootstrap confidence interval crosses zero",
  t_stat_below_threshold: "t-stat below the validation threshold",
  oos_degradation_exceeds_limit: "Degrades too much out-of-sample vs in-sample",
  insufficient_oos_rows: "Too few out-of-sample rows to validate",
  insufficient_correlation_clusters: "Too few uncorrelated event clusters",
  missing_closing_line: "No closing line on record for these rows",
  missing_locked_forecast: "No locked forecast for this market yet",
  insufficient_factor_provenance: "Factor inputs were not captured on the rows",
};

/** Human read of a validator rejection code (falls back to the raw code). */
export function alphaRejectionLabel(reason: string | null): string {
  if (!reason) return "No reason recorded";
  return REJECTION_LABELS[reason] ?? reason.replaceAll("_", " ");
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

function asStringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function normalizeRejection(raw: unknown): AlphaRejection | null {
  const rec = asRecord(raw);
  const name = asStringOrNull(rec.name);
  if (!name) return null;
  return { name, reason: asStringOrNull(rec.reason) };
}

function normalizeFactor(raw: unknown, index: number): AlphaFactor | null {
  const rec = asRecord(raw);
  const name = asStringOrNull(rec.name) ?? `factor_${index + 1}`;
  const prov = asRecord(rec.provenance);
  return {
    name,
    score: asFiniteNumber(rec.score) ?? 0,
    valid: rec.valid === true,
    t_stat: asFiniteNumber(rec.t_stat),
    reason: asStringOrNull(rec.reason),
    provenance: {
      available: prov.available !== false,
      reason: asStringOrNull(prov.reason),
      fields: Array.isArray(prov.fields)
        ? prov.fields.filter((f): f is string => typeof f === "string")
        : [],
    },
  };
}

function normalizeFactors(raw: unknown): AlphaFactors | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.factors)) return null;
  const factors = rec.factors
    .map((f, i) => normalizeFactor(f, i))
    .filter((f): f is AlphaFactor => f !== null);
  if (factors.length === 0) return null;
  const rejected = Array.isArray(rec.rejected_factors)
    ? rec.rejected_factors
        .map(normalizeRejection)
        .filter((r): r is AlphaRejection => r !== null)
    : factors
        .filter((f) => !f.valid && f.reason)
        .map((f) => ({ name: f.name, reason: f.reason }));
  return {
    market: asStringOrNull(rec.market) ?? ALPHA_CANONICAL_MARKET,
    as_of: asStringOrNull(rec.as_of),
    factors,
    rejected_factors: rejected,
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

function normalizeReportFactor(raw: unknown, index: number): AlphaReportFactor | null {
  const rec = asRecord(raw);
  const name = asStringOrNull(rec.name) ?? `factor_${index + 1}`;
  return {
    name,
    valid: rec.valid === true,
    reason: asStringOrNull(rec.reason),
    count: asFiniteNumber(rec.count) ?? 0,
    t_stat: asFiniteNumber(rec.t_stat),
    is_brier: asFiniteNumber(rec.is_brier),
    oos_brier: asFiniteNumber(rec.oos_brier),
    closing_brier: asFiniteNumber(rec.closing_brier),
    brier_delta_vs_closing: asFiniteNumber(rec.brier_delta_vs_closing),
    bootstrap_lower: asFiniteNumber(rec.bootstrap_lower),
    oos_degradation: asFiniteNumber(rec.oos_degradation),
    oos_count: asFiniteNumber(rec.oos_count),
    correlation_clusters: asFiniteNumber(rec.correlation_clusters),
  };
}

function normalizeReport(raw: unknown): AlphaReport | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.factors)) return null;
  const factors = rec.factors
    .map((f, i) => normalizeReportFactor(f, i))
    .filter((f): f is AlphaReportFactor => f !== null);
  if (factors.length === 0) return null;
  return {
    factors,
    valid_factor_count:
      asFiniteNumber(rec.valid_factor_count) ??
      factors.filter((f) => f.valid).length,
    rejected_factors: Array.isArray(rec.rejected_factors)
      ? rec.rejected_factors
          .map(normalizeRejection)
          .filter((r): r is AlphaRejection => r !== null)
      : factors
          .filter((f) => !f.valid && f.reason)
          .map((f) => ({ name: f.name, reason: f.reason })),
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live alpha API is absent)
// ---------------------------------------------------------------------------

const MOCK_AS_OF = "2026-07-23T12:00:00.000Z";

type MockFactorSeed = {
  name: string;
  score: number;
  valid: boolean;
  t_stat: number | null;
  reason: string | null;
  provReason?: string;
  stats?: {
    is_brier: number;
    oos_brier: number;
    closing_brier: number;
    brier_delta_vs_closing: number;
    bootstrap_lower: number;
    oos_degradation: number | null;
    oos_count: number;
    correlation_clusters: number;
  };
};

const MOCK_FACTOR_SEEDS: MockFactorSeed[] = [
  {
    name: "model_edge",
    score: 0.42,
    valid: true,
    t_stat: 2.31,
    reason: null,
    stats: {
      is_brier: 0.213,
      oos_brier: 0.221,
      closing_brier: 0.236,
      brier_delta_vs_closing: 0.015,
      bootstrap_lower: 0.004,
      oos_degradation: 0.038,
      oos_count: 41,
      correlation_clusters: 9,
    },
  },
  {
    name: "time_decay",
    score: 0.27,
    valid: true,
    t_stat: 2.62,
    reason: null,
    stats: {
      is_brier: 0.219,
      oos_brier: 0.224,
      closing_brier: 0.238,
      brier_delta_vs_closing: 0.014,
      bootstrap_lower: 0.006,
      oos_degradation: 0.023,
      oos_count: 41,
      correlation_clusters: 11,
    },
  },
  {
    name: "whale_flow",
    score: 0.18,
    valid: true,
    t_stat: 2.05,
    reason: null,
    stats: {
      is_brier: 0.221,
      oos_brier: 0.229,
      closing_brier: 0.235,
      brier_delta_vs_closing: 0.006,
      bootstrap_lower: 0.001,
      oos_degradation: 0.036,
      oos_count: 38,
      correlation_clusters: 8,
    },
  },
  {
    name: "momentum",
    score: 0.11,
    valid: false,
    t_stat: 0.82,
    reason: "oos_does_not_beat_closing",
    stats: {
      is_brier: 0.207,
      oos_brier: 0.241,
      closing_brier: 0.237,
      brier_delta_vs_closing: -0.004,
      bootstrap_lower: -0.009,
      oos_degradation: 0.164,
      oos_count: 41,
      correlation_clusters: 9,
    },
  },
  {
    name: "cross_venue",
    score: 0.03,
    valid: false,
    t_stat: 1.44,
    reason: "bootstrap_ci_not_positive",
    stats: {
      is_brier: 0.224,
      oos_brier: 0.231,
      closing_brier: 0.234,
      brier_delta_vs_closing: 0.003,
      bootstrap_lower: -0.002,
      oos_degradation: 0.031,
      oos_count: 29,
      correlation_clusters: 6,
    },
  },
  {
    name: "news_sentiment",
    score: 0.09,
    valid: false,
    t_stat: 1.21,
    reason: "insufficient_correlation_clusters",
    stats: {
      is_brier: 0.226,
      oos_brier: 0.233,
      closing_brier: 0.236,
      brier_delta_vs_closing: 0.003,
      bootstrap_lower: 0.001,
      oos_degradation: 0.031,
      oos_count: 22,
      correlation_clusters: 1,
    },
  },
  {
    name: "mean_reversion",
    score: -0.06,
    valid: false,
    t_stat: null,
    reason: "insufficient_oos_rows",
    stats: {
      is_brier: 0.231,
      oos_brier: 0.244,
      closing_brier: 0.239,
      brier_delta_vs_closing: -0.005,
      bootstrap_lower: -0.012,
      oos_degradation: 0.056,
      oos_count: 7,
      correlation_clusters: 3,
    },
  },
];

function mockFactor(seed: MockFactorSeed): AlphaFactor {
  return {
    name: seed.name,
    score: seed.score,
    valid: seed.valid,
    t_stat: seed.t_stat,
    reason: seed.reason,
    provenance: {
      available: true,
      reason: seed.provReason ?? null,
      fields: ["model_probability", "market_implied_probability"],
    },
  };
}

function buildMockFactors(): AlphaFactors {
  const factors = MOCK_FACTOR_SEEDS.map(mockFactor);
  return {
    market: ALPHA_CANONICAL_MARKET,
    as_of: MOCK_AS_OF,
    factors,
    rejected_factors: factors
      .filter((f) => !f.valid)
      .map((f) => ({ name: f.name, reason: f.reason })),
    paper_trading_only: true,
  };
}

function buildMockReport(): AlphaReport {
  const factors: AlphaReportFactor[] = MOCK_FACTOR_SEEDS.map((seed) => ({
    name: seed.name,
    valid: seed.valid,
    reason: seed.reason,
    count: (seed.stats?.oos_count ?? 0) + 61,
    t_stat: seed.t_stat,
    is_brier: seed.stats?.is_brier ?? null,
    oos_brier: seed.stats?.oos_brier ?? null,
    closing_brier: seed.stats?.closing_brier ?? null,
    brier_delta_vs_closing: seed.stats?.brier_delta_vs_closing ?? null,
    bootstrap_lower: seed.stats?.bootstrap_lower ?? null,
    oos_degradation: seed.stats?.oos_degradation ?? null,
    oos_count: seed.stats?.oos_count ?? null,
    correlation_clusters: seed.stats?.correlation_clusters ?? null,
  }));
  return {
    factors,
    valid_factor_count: factors.filter((f) => f.valid).length,
    rejected_factors: factors
      .filter((f) => !f.valid)
      .map((f) => ({ name: f.name, reason: f.reason })),
    paper_trading_only: true,
  };
}

/** Canonical seeded payloads — exported for fixtures and offline fallback. */
export const MOCK_ALPHA_FACTORS: AlphaFactors = buildMockFactors();
export const MOCK_ALPHA_REPORT: AlphaReport = buildMockReport();

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the alpha API)
// ---------------------------------------------------------------------------

type AlphaFetch = typeof fetch;

let alphaFetch: AlphaFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setAlphaFetch(fn: AlphaFetch): void {
  alphaFetch = fn;
}

/** Restore the default fetch layer (test hygiene). */
export function resetAlphaFetch(): void {
  alphaFetch = (...args) => fetch(...args);
}

async function tryLiveJson<T>(
  path: string,
  token: string | null,
): Promise<T | null> {
  const base = (await ensureApiBase()) || undefined;
  if (!base || !hasLiveApi(base)) return null;
  try {
    const res = await alphaFetch(apiUrl(path, base), {
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
 * Factor scores + independent validation for one market.
 * Live first; paper mock fallback. Never rejects.
 */
export async function fetchAlphaFactors(
  market: string = ALPHA_CANONICAL_MARKET,
  token: string | null = null,
): Promise<{ data: AlphaFactors; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/alpha/factors?market=${encodeURIComponent(market)}`,
    token,
  );
  const normalized = normalizeFactors(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: buildMockFactors(), source: "mock" };
}

/**
 * Portfolio-wide validated-factor report (which factors beat the closing
 * line out-of-sample). Live first; paper mock fallback. Never rejects.
 */
export async function fetchAlphaReport(
  token: string | null = null,
): Promise<{ data: AlphaReport; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/report", token);
  const normalized = normalizeReport(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: buildMockReport(), source: "mock" };
}
