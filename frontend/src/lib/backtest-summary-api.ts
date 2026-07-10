import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * D02: walk-forward backtest transparency — GET /api/v1/backtest/summary
 * (backend H02). Brier + flat-stake paper ROI over REAL resolved external
 * markets (ForecastLog × ForecastScore), same source as /track-record. No
 * params, read-only. Honest empties at n=0; thin_data must be caveated.
 * See goals/loop-v3/API-NOTES.md → H02.
 */

export type WalkForwardPoint = {
  seq: number;
  scored_at: string;
  brier: number;
  cumulative_brier: number;
  cumulative_roi: number | null;
};

export type BacktestSummary = {
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

export type BacktestSummaryView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  /** False at n=0 — render the honest empty, no fabricated curve. */
  available: boolean;
  nLabel: string;
  /** Provisional caveat when thin_data, else null. */
  caveat: string | null;
  brierLabel: string;
  marketBrierLabel: string;
  /** "model beats market" | "market beats model" | null when incomparable. */
  brierVerdict: string | null;
  roiLabel: string;
  roiTone: "up" | "down" | "neutral";
  betsLabel: string;
  pnlLabel: string;
  brierSeries: SeriesPoint[];
  /** Only points after the first bet — cumulative_roi is null before that. */
  roiSeries: SeriesPoint[];
  hasBrierSeries: boolean;
  hasRoiSeries: boolean;
  lastUpdatedLabel: string | null;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Walk-forward research metrics from real resolutions only — paper trading, simulated funds, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function emptyView(reachable: boolean, disclaimer: string): BacktestSummaryView {
  return {
    reachable,
    available: false,
    nLabel: "0",
    caveat: null,
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

/** Pure transform: raw H02 response → view model. Honest empty at n=0. */
export function buildBacktestSummaryView(raw: BacktestSummary | null): BacktestSummaryView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) return emptyView(false, disclaimer);
  if (!isFiniteNum(raw.n) || raw.n <= 0) return emptyView(true, disclaimer);

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
  const marketBrier = isFiniteNum(raw.market_brier_score) ? raw.market_brier_score : null;
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

  const threshold = isFiniteNum(raw.thin_data_threshold) ? raw.thin_data_threshold : 30;

  return {
    reachable: true,
    available: true,
    nLabel: String(raw.n),
    caveat: raw.thin_data
      ? `Only ${raw.n} resolved forecast${raw.n === 1 ? "" : "s"} (threshold ${threshold}) — treat every number below as provisional.`
      : null,
    brierLabel: brier === null ? "—" : brier.toFixed(4),
    marketBrierLabel: marketBrier === null ? "—" : marketBrier.toFixed(4),
    brierVerdict,
    roiLabel: roi === null ? "no bets placed" : `${roi >= 0 ? "+" : ""}${(roi * 100).toFixed(1)}%`,
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
// Fetch
// ---------------------------------------------------------------------------

/** Fetch the walk-forward summary. Returns null with no live API or on error. */
export async function fetchBacktestSummary(
  signal?: AbortSignal,
): Promise<BacktestSummary | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/backtest/summary", base), {
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as BacktestSummary;
  } catch {
    return null;
  }
}
