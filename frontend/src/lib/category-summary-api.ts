import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import {
  buildOpportunityRowView,
  type OpportunityRow,
  type OpportunityRowView,
} from "@/lib/opportunities-api";

/**
 * S02/O02: category intelligence aggregate — GET
 * /api/v1/categories/{category}/summary (backend O02). A per-category, READ-ONLY
 * composition of existing surfaces: market count, mean absolute edge, top N01
 * opportunities, recent signal count, and the O01 resolved-market accuracy.
 *
 * CONTRACT (see goals/loop-v10/API-NOTES.md → O02). Unknown/empty category →
 * honest `{found:false}` with zeros — nothing is fabricated.
 */

// ── Raw response (matches API-NOTES.md → O02) ────────────────────────────────

export type CategorySummaryResponse = {
  category: string;
  found: boolean;
  market_count: number;
  mean_abs_edge: number | null;
  top_opportunities: OpportunityRow[];
  recent_signal_count: number;
  resolved_n: number;
  resolved_accuracy: number | null;
  paper_trading_only?: boolean;
  signal_only?: boolean;
  disclaimer?: string;
  generated_at?: string;
  cached?: boolean;
};

// ── View model (pure — unit-tested) ──────────────────────────────────────────

export type CategorySummaryView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  /** Honest false when the category has no data (200 {found:false}). */
  found: boolean;
  category: string;
  marketCount: number;
  /** "12.0 pts" mean absolute edge, or "—" when none. */
  meanEdgeLabel: string;
  meanAbsEdge: number | null;
  topOpportunities: OpportunityRowView[];
  recentSignalCount: number;
  resolvedN: number;
  /** "75%" resolved accuracy, or "—" when resolved_n=0. */
  resolvedAccuracyLabel: string;
  resolvedAccuracy: number | null;
  disclaimer: string;
  cached: boolean;
};

const FALLBACK_DISCLAIMER =
  "Category intelligence — a read-only per-category aggregate of the desk's model-vs-market edges, signals and resolved track record. Paper trading only, simulated funds, no execution. NOT an order feed.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function ptsLabel(v: number | null): string {
  return isFiniteNum(v) ? `${(v * 100).toFixed(1)} pts` : "—";
}

function intOrZero(v: unknown): number {
  return isFiniteNum(v) ? Math.max(0, Math.round(v)) : 0;
}

/**
 * Pure transform: raw O02 response → view model. Honest unreachable / not-found
 * / empty states; the top-opportunity rows reuse the R01 row builder so they
 * render identically to the scanner. Nothing is fabricated.
 */
export function buildCategorySummaryView(
  raw: CategorySummaryResponse | null,
  requestedCategory = "",
): CategorySummaryView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) {
    return {
      reachable: false,
      found: false,
      category: requestedCategory,
      marketCount: 0,
      meanEdgeLabel: "—",
      meanAbsEdge: null,
      topOpportunities: [],
      recentSignalCount: 0,
      resolvedN: 0,
      resolvedAccuracyLabel: "—",
      resolvedAccuracy: null,
      disclaimer,
      cached: false,
    };
  }

  const meanAbsEdge = isFiniteNum(raw.mean_abs_edge) ? raw.mean_abs_edge : null;
  const resolvedAccuracy = isFiniteNum(raw.resolved_accuracy) ? raw.resolved_accuracy : null;
  const opps = Array.isArray(raw.top_opportunities) ? raw.top_opportunities : [];

  return {
    reachable: true,
    found: raw.found === true,
    category:
      typeof raw.category === "string" && raw.category.trim()
        ? raw.category
        : requestedCategory,
    marketCount: intOrZero(raw.market_count),
    meanEdgeLabel: ptsLabel(meanAbsEdge),
    meanAbsEdge,
    topOpportunities: opps.map(buildOpportunityRowView),
    recentSignalCount: intOrZero(raw.recent_signal_count),
    resolvedN: intOrZero(raw.resolved_n),
    resolvedAccuracyLabel: resolvedAccuracy === null ? "—" : pct(resolvedAccuracy),
    resolvedAccuracy,
    disclaimer,
    cached: raw.cached === true,
  };
}

// ── Network (reuses the shared alphaedge-api base resolver; no poll loop) ─────

/**
 * Fetch the per-category intelligence aggregate. PUBLIC GET (no auth). Returns
 * null with no live API / on a transport error (unreachable). An unknown
 * category is an honest 200 {found:false}, not an error.
 */
export async function fetchCategorySummary(
  category: string,
  opts?: { signal?: AbortSignal },
): Promise<CategorySummaryResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(
      apiUrl(`/api/v1/categories/${encodeURIComponent(category)}/summary`, base),
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as CategorySummaryResponse;
  } catch {
    return null;
  }
}
