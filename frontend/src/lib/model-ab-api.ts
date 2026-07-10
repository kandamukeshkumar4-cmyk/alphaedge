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

export type ResolvedCountResponse = {
  resolved_count: number;
  ab_threshold: number;
  ab_ready: boolean;
  model_default: string;
  paper_trading_only: boolean;
};

export type ModelAbState = "loading" | "not-ready" | "lgbm-unavailable" | "ready";

export type ModelAbView = {
  state: ModelAbState;
  resolvedCount: number;
  threshold: number;
  progressPct: number;
  remaining: number;
  resolvedLabel: string;
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
  const threshold = num(resolved?.ab_threshold) ?? num(ab?.threshold) ?? 100;
  const resolvedCount = num(resolved?.resolved_count) ?? num(ab?.resolved_count) ?? 0;
  const defaultModel = resolved?.model_default ?? ab?.model_default ?? null;
  const progressPct = threshold > 0 ? Math.max(0, Math.min(100, (resolvedCount / threshold) * 100)) : 0;
  const remaining = Math.max(0, threshold - resolvedCount);

  const base = {
    resolvedCount,
    threshold,
    progressPct,
    remaining,
    resolvedLabel: `${resolvedCount} / ${threshold} resolved`,
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
