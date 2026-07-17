import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

/**
 * W03 — Model A/B readout client (backend J03 GET /api/v1/system/model-ab and
 * I02 GET /api/v1/system/resolved-count).
 *
 * The walk-forward LightGBM-vs-XGBoost harness NEVER flips the deployed default
 * model — it is analysis only (`applied: false`). Below the resolve threshold
 * the endpoint reports `ready: false`; if lightgbm is missing from the image it
 * honestly flags `lightgbm_available: false` and reports XGB-only. All labelling
 * is pure and tolerant of absent fields; we never fabricate a Brier.
 */
export type ModelAbResponse = {
  ready: boolean;
  resolved_count?: number | null;
  threshold?: number | null;
  lightgbm_available?: boolean;
  xgb_brier?: number | null;
  lgbm_brier?: number | null;
  delta?: number | null;
  which_would_win?: string | null;
  applied?: boolean;
  model_default?: string | null;
};

/** Population that produced ``resolved_count`` (V33 B2'c disclosure). */
export type ResolvedCountSource = "forecast_scores" | "paper_orders_fallback" | string;

export type PopulationHistogramEntry = {
  key: string;
  n: number;
  share: number;
};

/** Backend-owned composition facts for the scored forecast population. */
export type ResolvedCountPopulation = {
  ab_cluster_threshold?: number | null;
  category_histogram?: PopulationHistogramEntry[] | null;
  family_histogram?: PopulationHistogramEntry[] | null;
  cluster_histogram?: PopulationHistogramEntry[] | null;
  effective_n_estimate?: number | null;
  effective_n_ratio?: number | null;
  horizon_hours?: Record<string, number> | null;
  checks?: Record<string, boolean> | null;
  verdict?: string | null;
};

export type ResolvedCountResponse = {
  resolved_count: number;
  /** Legacy threshold name. It is safe for cluster progress only alongside correlation_clusters. */
  ab_threshold?: number | null;
  /** V53 cluster-gate threshold. */
  ab_cluster_threshold?: number | null;
  /** V53 effective independent-population numerator. */
  correlation_clusters?: number | null;
  ab_ready: boolean;
  model_default: string;
  paper_trading_only: boolean;
  /** Which population ``resolved_count`` came from. Absent on older backends. */
  source?: ResolvedCountSource | null;
  /** Scored LIVE ForecastLog rows — may be 0 while resolved_count > 0 via fallback. */
  forecast_scored_count?: number | null;
  population?: ResolvedCountPopulation | null;
};

/** Honest, user-facing labels for the resolved-count disclosure fields. */
export type ResolvedCountDisclosure = {
  resolvedCount: number;
  forecastScoredCount: number | null;
  source: ResolvedCountSource | null;
  sourceLabel: string;
  sourceDetail: string;
  /** True when resolved_count is backed by paper orders, not scored forecasts. */
  isPaperOrdersFallback: boolean;
};

export function buildResolvedCountDisclosure(
  resolved: ResolvedCountResponse | null,
): ResolvedCountDisclosure | null {
  if (!resolved) return null;
  const resolvedCount = num(resolved.resolved_count) ?? 0;
  const forecastScored =
    resolved.forecast_scored_count === undefined || resolved.forecast_scored_count === null
      ? null
      : num(resolved.forecast_scored_count);
  const source =
    typeof resolved.source === "string" && resolved.source.trim()
      ? resolved.source.trim()
      : null;
  const isPaperOrdersFallback = source === "paper_orders_fallback";

  let sourceLabel: string;
  let sourceDetail: string;
  if (source === "forecast_scores") {
    sourceLabel = "Scored LIVE forecasts";
    sourceDetail =
      "resolved_count counts scored LIVE ForecastLog rows on resolved external markets.";
  } else if (source === "paper_orders_fallback") {
    sourceLabel = "Paper-order fallback";
    sourceDetail =
      "No scored forecasts yet — resolved_count falls back to resolved paper-order markets (a different population).";
  } else if (source) {
    sourceLabel = source;
    sourceDetail = `Population source reported as "${source}".`;
  } else {
    sourceLabel = "Source undisclosed";
    sourceDetail =
      "This API build did not return source / forecast_scored_count — showing resolved_count only.";
  }

  return {
    resolvedCount,
    forecastScoredCount: forecastScored,
    source,
    sourceLabel,
    sourceDetail,
    isPaperOrdersFallback,
  };
}

export type ModelAbState = "loading" | "not-ready" | "lgbm-unavailable" | "ready";

export type ModelAbView = {
  state: ModelAbState;
  clusterCount: number | null;
  clusterThreshold: number | null;
  progressPct: number | null;
  remaining: number | null;
  clusterLabel: string;
  forecastScoredCount: number | null;
  defaultModelLabel: string;
  /** Always true — the harness never changes the deployed model. */
  defaultUnchanged: boolean;
  xgbBrierLabel: string;
  lgbmBrierLabel: string;
  deltaLabel: string | null;
  winnerLabel: string | null;
  unavailableNote: string | null;
};

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function brierLabel(value: number | null): string {
  return value === null ? "—" : value.toFixed(4);
}

function titleCase(model: string | null | undefined): string {
  if (!model) return "—";
  return model.charAt(0).toUpperCase() + model.slice(1);
}

/**
 * Pure: compose the resolved-count readout and the A/B result into one view.
 * `resolved-count` (I02) is the authority for the progress bar; the A/B body
 * (J03) supplies the Briers once ready.
 */
export function buildModelAbView(
  ab: ModelAbResponse | null,
  resolved: ResolvedCountResponse | null,
): ModelAbView {
  const clusterCount = num(resolved?.correlation_clusters);
  const hasRawClusterCount =
    resolved?.correlation_clusters !== undefined && resolved?.correlation_clusters !== null;
  const clusterThreshold =
    num(resolved?.ab_cluster_threshold) ??
    num(resolved?.population?.ab_cluster_threshold) ??
    (hasRawClusterCount ? num(resolved?.ab_threshold) : null);
  const hasClusterProgress =
    clusterCount !== null && clusterThreshold !== null && clusterThreshold > 0;
  const progressPct = hasClusterProgress
    ? Math.max(0, Math.min(100, (clusterCount / clusterThreshold) * 100))
    : null;
  const remaining = hasClusterProgress ? Math.max(0, clusterThreshold - clusterCount) : null;
  const forecastScoredCount = num(resolved?.forecast_scored_count);
  const defaultModel = resolved?.model_default ?? ab?.model_default ?? null;

  const base = {
    clusterCount,
    clusterThreshold,
    progressPct,
    remaining,
    clusterLabel: hasClusterProgress
      ? `${clusterCount} / ${clusterThreshold} correlation clusters`
      : "Cluster data unavailable",
    forecastScoredCount,
    defaultModelLabel: titleCase(defaultModel),
    defaultUnchanged: true,
    xgbBrierLabel: "—",
    lgbmBrierLabel: "—",
    deltaLabel: null as string | null,
    winnerLabel: null as string | null,
    unavailableNote: null as string | null,
  };

  if (ab === null && resolved === null) {
    return { ...base, state: "loading" };
  }

  if (!ab || !ab.ready) {
    return { ...base, state: "not-ready" };
  }

  const xgb = num(ab.xgb_brier);
  const lgbm = num(ab.lgbm_brier);

  // lightgbm not in the image → honest XGB-only.
  if (ab.lightgbm_available === false || lgbm === null) {
    return {
      ...base,
      state: "lgbm-unavailable",
      xgbBrierLabel: brierLabel(xgb),
      unavailableNote:
        "LightGBM is not available in this deployment image — reporting XGBoost only. The default model is unchanged.",
    };
  }

  const delta = num(ab.delta) ?? (xgb !== null && lgbm !== null ? xgb - lgbm : null);
  const winner =
    ab.which_would_win ??
    (xgb !== null && lgbm !== null ? (xgb < lgbm ? "xgboost" : lgbm < xgb ? "lightgbm" : "tie") : null);

  return {
    ...base,
    state: "ready",
    xgbBrierLabel: brierLabel(xgb),
    lgbmBrierLabel: brierLabel(lgbm),
    deltaLabel: delta === null ? null : `${delta >= 0 ? "+" : ""}${delta.toFixed(4)}`,
    winnerLabel: winner === "tie" ? "Tie" : winner ? titleCase(winner) : null,
  };
}

// ── Network ─────────────────────────────────────────────────────────────────

export async function fetchResolvedCount(): Promise<ResolvedCountResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/system/resolved-count", base), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as ResolvedCountResponse;
  } catch {
    return null;
  }
}

export async function fetchModelAb(): Promise<ModelAbResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/system/model-ab", base), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as ModelAbResponse;
  } catch {
    return null;
  }
}
