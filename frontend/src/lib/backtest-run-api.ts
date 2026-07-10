import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * X01: self-serve per-market backtest — GET /api/v1/backtest/run?slug=
 * (backend K01). Deterministic walk-forward Brier + flat-stake ROI for ONE
 * resolved market's forecast history, reusing the same source + bet math as
 * /backtest/summary. PUBLIC GET, read-only, bounded compute.
 *
 * The endpoint NEVER 5xxes: any failure degrades to an honest
 * `{ran:false, reason, slug}` at HTTP 200. This view model surfaces that reason
 * verbatim (unknown slug / thin data / too few resolves) — never a fake curve.
 * See goals/loop-v6/API-NOTES.md → K01.
 */

export type WalkForwardPoint = {
  seq: number;
  scored_at: string;
  brier: number;
  cumulative_brier: number;
  cumulative_roi: number | null;
};

export type BacktestRunReason =
  | "empty_slug"
  | "unknown_slug"
  | "too_few_resolves"
  | "compute_error";

export type BacktestRunResponse = {
  ran: boolean;
  slug: string;
  reason: BacktestRunReason | string | null;
  n: number;
  thin_data: boolean;
  thin_data_threshold: number;
  brier_score: number | null;
  market_brier_score: number | null;
  roi: number | null;
  n_bets: number;
  total_pnl: number;
  total_staked: number;
  walk_forward: WalkForwardPoint[];
  source: string;
  last_updated: string | null;
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
};

// ---------------------------------------------------------------------------
// View model (pure — unit-tested)
// ---------------------------------------------------------------------------

export type SeriesPoint = { seq: number; value: number };

export type BacktestRunStatus = "ran" | "not-ran" | "unreachable";

export type BacktestRunView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  /** True only when the endpoint actually produced metrics. */
  ran: boolean;
  status: BacktestRunStatus;
  slug: string;
  /** Honest human message when not ran (unknown slug / too few resolves…). */
  notRanMessage: string | null;
  /** Provisional caveat when thin_data (ran but n below threshold), else null. */
  caveat: string | null;
  nLabel: string;
  brierLabel: string;
  marketBrierLabel: string;
  /** "model beats market" | "market beats model" | "model ties market" | null. */
  brierVerdict: string | null;
  roiLabel: string;
  roiTone: "up" | "down" | "neutral";
  betsLabel: string;
  pnlLabel: string;
  brierSeries: SeriesPoint[];
  roiSeries: SeriesPoint[];
  hasBrierSeries: boolean;
  hasRoiSeries: boolean;
  lastUpdatedLabel: string | null;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Self-serve walk-forward research metrics from real resolutions only — paper trading, simulated funds, no execution.";

const REASON_MESSAGE: Record<BacktestRunReason, string> = {
  empty_slug: "Pick a market to run a walk-forward backtest.",
  unknown_slug:
    "No resolved forecast history for that market — self-serve backtests only run on markets this desk has already forecast and that have settled.",
  too_few_resolves:
    "Too few resolved forecasts on this market to backtest yet (need at least 3). Nothing is fabricated — check back after more of its questions settle.",
  compute_error:
    "The backtest could not be computed for this market. No partial or fabricated result is shown.",
};

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function notRanView(
  reachable: boolean,
  slug: string,
  reason: string | null,
  disclaimer: string,
): BacktestRunView {
  const message = reachable
    ? (reason && REASON_MESSAGE[reason as BacktestRunReason]) ||
      "This market cannot be backtested right now."
    : null;
  return {
    reachable,
    ran: false,
    status: reachable ? "not-ran" : "unreachable",
    slug,
    notRanMessage: message,
    caveat: null,
    nLabel: "0",
    brierLabel: "—",
    marketBrierLabel: "—",
    brierVerdict: null,
    roiLabel: "—",
    roiTone: "neutral",
    betsLabel: "0",
    pnlLabel: "—",
    brierSeries: [],
    roiSeries: [],
    hasBrierSeries: false,
    hasRoiSeries: false,
    lastUpdatedLabel: null,
    disclaimer,
  };
}

/** Pure transform: raw K01 response → view model. Honest not-ran surfacing. */
export function buildBacktestRunView(
  raw: BacktestRunResponse | null,
): BacktestRunView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) return notRanView(false, "", null, disclaimer);
  const slug = typeof raw.slug === "string" ? raw.slug : "";
  if (!raw.ran || !isFiniteNum(raw.n) || raw.n <= 0) {
    return notRanView(true, slug, raw.reason ?? null, disclaimer);
  }

  const wf = Array.isArray(raw.walk_forward) ? raw.walk_forward : [];
  const brierSeries: SeriesPoint[] = wf
    .filter((p) => isFiniteNum(p.cumulative_brier))
    .map((p) => ({ seq: p.seq, value: p.cumulative_brier }));
  const roiSeries: SeriesPoint[] = wf
    .filter((p): p is WalkForwardPoint & { cumulative_roi: number } =>
      isFiniteNum(p.cumulative_roi),
    )
    .map((p) => ({ seq: p.seq, value: p.cumulative_roi }));

  const brier = isFiniteNum(raw.brier_score) ? raw.brier_score : null;
  const marketBrier = isFiniteNum(raw.market_brier_score)
    ? raw.market_brier_score
    : null;
  const roi = isFiniteNum(raw.roi) ? raw.roi : null;

  let brierVerdict: string | null = null;
  if (brier !== null && marketBrier !== null) {
    brierVerdict =
      brier < marketBrier
        ? "model beats market"
        : brier > marketBrier
          ? "market beats model"
          : "model ties market";
  }

  const threshold = isFiniteNum(raw.thin_data_threshold)
    ? raw.thin_data_threshold
    : 30;

  return {
    reachable: true,
    ran: true,
    status: "ran",
    slug,
    notRanMessage: null,
    caveat: raw.thin_data
      ? `Only ${raw.n} resolved forecast${raw.n === 1 ? "" : "s"} (threshold ${threshold}) — treat every number below as provisional.`
      : null,
    nLabel: String(raw.n),
    brierLabel: brier === null ? "—" : brier.toFixed(4),
    marketBrierLabel: marketBrier === null ? "—" : marketBrier.toFixed(4),
    brierVerdict,
    roiLabel:
      roi === null
        ? "no bets placed"
        : `${roi >= 0 ? "+" : ""}${(roi * 100).toFixed(1)}%`,
    roiTone: roi === null ? "neutral" : roi >= 0 ? "up" : "down",
    betsLabel: String(isFiniteNum(raw.n_bets) ? raw.n_bets : 0),
    pnlLabel: isFiniteNum(raw.total_pnl)
      ? `${raw.total_pnl >= 0 ? "+" : "-"}$${Math.abs(raw.total_pnl).toFixed(2)}`
      : "—",
    brierSeries,
    roiSeries,
    hasBrierSeries: brierSeries.length >= 2,
    hasRoiSeries: roiSeries.length >= 2,
    lastUpdatedLabel: raw.last_updated
      ? new Date(raw.last_updated).toLocaleDateString()
      : null,
    disclaimer,
  };
}

// ---------------------------------------------------------------------------
// Strategy params (Y01 — L01 edge_threshold + stake)
// ---------------------------------------------------------------------------

/**
 * Optional, deterministic strategy knobs for the self-serve backtest (backend
 * L01). Both are additive and read-only:
 *  - `edgeThreshold`: minimum |model_p − market_p| edge to place a paper bet.
 *    Only ever RAISES the bet gate. Omit (or null) → K01 default gate.
 *  - `stake`: flat stake per bet; scales P&L + staked, ROI is stake-invariant.
 *    Omit (or null) → default 1.0.
 *
 * The backend clamps out-of-range values (never 422/5xx); we still bound them
 * here so the query we send is honest about what the desk will actually run.
 */
export type BacktestRunParams = {
  edgeThreshold?: number | null;
  stake?: number | null;
};

export const EDGE_THRESHOLD_MIN = 0;
export const EDGE_THRESHOLD_MAX = 1;
export const STAKE_MIN = 0.01;
export const STAKE_MAX = 1000;

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/**
 * Pure: build the query string for a self-serve backtest run. A param is only
 * emitted when it is a finite number; omitting BOTH reproduces the K01 default
 * request byte-for-byte (the invariant the backend regression-tests). Values are
 * clamped to the documented L01 ranges before they leave the browser.
 */
export function buildBacktestRunQuery(
  slug: string,
  params?: BacktestRunParams,
): URLSearchParams {
  const q = new URLSearchParams({ slug: slug.trim() });
  const edge = params?.edgeThreshold;
  if (typeof edge === "number" && Number.isFinite(edge)) {
    q.set("edge_threshold", String(clamp(edge, EDGE_THRESHOLD_MIN, EDGE_THRESHOLD_MAX)));
  }
  const stake = params?.stake;
  if (typeof stake === "number" && Number.isFinite(stake)) {
    q.set("stake", String(clamp(stake, STAKE_MIN, STAKE_MAX)));
  }
  return q;
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

/**
 * Run a self-serve backtest for one market slug, optionally with L01 strategy
 * params (edge threshold + stake). Returns null with no live API or on a
 * transport error; the endpoint itself never 5xxes (honest not-ran body at HTTP
 * 200), so a null here means "unreachable", not "not-ran".
 */
export async function fetchBacktestRunForSlug(
  slug: string,
  params?: BacktestRunParams,
  signal?: AbortSignal,
): Promise<BacktestRunResponse | null> {
  const trimmed = slug.trim();
  if (!trimmed) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const query = buildBacktestRunQuery(trimmed, params);
    const res = await fetch(
      `${apiUrl("/api/v1/backtest/run", base)}?${query.toString()}`,
      { cache: "no-store", signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as BacktestRunResponse;
  } catch {
    return null;
  }
}
