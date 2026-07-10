import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import { marketHref } from "@/lib/market-href";
import type { NewsEvidence, SignalEvidence } from "@/lib/signal-evidence";

/**
 * R01: opportunity scanner — GET /api/v1/opportunities (backend N01). A ranked,
 * READ-ONLY view of the markets where the model most disagrees with the market
 * ("the biggest edges right now"). Analysis only — NEVER an order feed.
 *
 * CONTRACT NOTE (see goals/loop-v9/API-NOTES.md): each row's `edge` here is the
 * ABSOLUTE gap `|model_p − market_p|` (the ranking key) — do NOT confuse it with
 * the SIGNED edge in the N03 edge-history series.
 */

/** H03 citation carried on a top-signal (family+citation). */
export type OpportunityCitation = {
  signal_id: string;
  news_id: string | null;
  news_url: string | null;
  headline: string | null;
  model_p: number | null;
  market_p: number | null;
};

export type OpportunityTopSignal = {
  family: string;
  citation: OpportunityCitation | null;
};

/** One raw N01 row. */
export type OpportunityRow = {
  slug: string;
  title: string;
  model_p: number;
  market_p: number;
  /** ABSOLUTE gap |model_p − market_p| — the rank key. */
  edge: number;
  direction: "YES" | "NO";
  yes_price: number | null;
  liquidity: number;
  top_signal: OpportunityTopSignal | null;
};

export type OpportunitiesResponse = {
  opportunities: OpportunityRow[];
  count: number;
  limit: number;
  min_liquidity: number;
  direction: string | null;
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
  generated_at: string;
  cached: boolean;
};

// ---------------------------------------------------------------------------
// View model (pure — unit-tested)
// ---------------------------------------------------------------------------

export type OpportunityRowView = {
  slug: string;
  title: string;
  /** "62%" — model P(YES). */
  modelLabel: string;
  /** "50%" — market-implied P(YES). */
  marketLabel: string;
  /** Absolute edge as points, e.g. "12.0 pts". */
  edgeLabel: string;
  /** Absolute edge fraction (0..1) for AnimatedNumber. */
  edge: number;
  direction: "YES" | "NO";
  directionTone: "up" | "down";
  /** "50%" or null when the row carries no displayed YES price. */
  yesPriceLabel: string | null;
  liquidity: number;
  /** "5.0K" compact liquidity. */
  liquidityLabel: string;
  family: string | null;
  evidence: SignalEvidence | null;
  href: string;
};

export type DirectionFilter = "all" | "YES" | "NO";

export type OpportunitiesView = {
  rows: OpportunityRowView[];
  /** Rows shown after client filters. */
  count: number;
  /** Rows available before client filters (for honest "filtered out" copy). */
  totalBeforeFilter: number;
  disclaimer: string;
  cached: boolean;
};

const FALLBACK_DISCLAIMER =
  "Opportunity scanner — ranked read-only view of model-vs-market edges. Signal only; paper trading only, simulated funds, no execution. This is NOT an order feed.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function compact(value: number): string {
  const v = isFiniteNum(value) ? value : 0;
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return String(Math.round(v));
}

/** Build renderable news evidence from a top-signal citation, or null. */
function citationEvidence(signal: OpportunityTopSignal | null): NewsEvidence | null {
  const citation = signal?.citation;
  if (!citation) return null;
  const headline =
    typeof citation.headline === "string" && citation.headline.trim().length > 0
      ? citation.headline
      : null;
  if (!headline) return null;
  const modelP = isFiniteNum(citation.model_p) ? citation.model_p : null;
  const marketP = isFiniteNum(citation.market_p) ? citation.market_p : null;
  const edge = modelP !== null && marketP !== null ? modelP - marketP : null;
  return {
    kind: "news",
    headline,
    url:
      typeof citation.news_url === "string" && citation.news_url.trim().length > 0
        ? citation.news_url
        : null,
    modelP,
    marketP,
    edgeLabel: edge === null ? null : `${edge >= 0 ? "+" : ""}${(edge * 100).toFixed(1)} pts`,
  };
}

/**
 * Build one renderable opportunity row view. Exported so the S02 category
 * dashboard renders the SAME row shape (from O02's `top_opportunities`) as the
 * R01 scanner — the two never diverge.
 */
export function buildOpportunityRowView(row: OpportunityRow): OpportunityRowView {
  const edge = isFiniteNum(row.edge) ? Math.abs(row.edge) : 0;
  const direction: "YES" | "NO" = row.direction === "NO" ? "NO" : "YES";
  return {
    slug: row.slug,
    title: row.title || row.slug,
    modelLabel: isFiniteNum(row.model_p) ? pct(row.model_p) : "—",
    marketLabel: isFiniteNum(row.market_p) ? pct(row.market_p) : "—",
    edgeLabel: `${(edge * 100).toFixed(1)} pts`,
    edge,
    direction,
    directionTone: direction === "YES" ? "up" : "down",
    yesPriceLabel: isFiniteNum(row.yes_price) ? pct(row.yes_price) : null,
    liquidity: isFiniteNum(row.liquidity) ? row.liquidity : 0,
    liquidityLabel: compact(row.liquidity),
    family: row.top_signal?.family ?? null,
    evidence: citationEvidence(row.top_signal ?? null),
    href: marketHref(row.slug),
  };
}

/**
 * Pure transform: raw N01 response → filtered, ranked view model. Client-side
 * `direction` + `minLiquidity` filters keep the controls instant without extra
 * fetches (the rows arrive pre-ranked by absolute edge from the backend).
 */
export function buildOpportunitiesView(
  raw: OpportunitiesResponse | null,
  opts?: { direction?: DirectionFilter; minLiquidity?: number },
): OpportunitiesView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  const rowsRaw = raw && Array.isArray(raw.opportunities) ? raw.opportunities : [];
  const all = rowsRaw.map(buildOpportunityRowView);
  const direction = opts?.direction ?? "all";
  const minLiquidity = isFiniteNum(opts?.minLiquidity) ? Math.max(0, opts!.minLiquidity!) : 0;
  const rows = all.filter((r) => {
    if (direction !== "all" && r.direction !== direction) return false;
    if (r.liquidity < minLiquidity) return false;
    return true;
  });
  return {
    rows,
    count: rows.length,
    totalBeforeFilter: all.length,
    disclaimer,
    cached: raw?.cached === true,
  };
}

// ---------------------------------------------------------------------------
// Fetch (reuses the shared alphaedge-api base resolver; no poll loop)
// ---------------------------------------------------------------------------

/** Fetch the opportunity scanner. Returns null with no live API or on error. */
export async function fetchOpportunities(
  opts?: { limit?: number; signal?: AbortSignal },
): Promise<OpportunitiesResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams();
  // Fetch a generous ranked set once; direction + min-liquidity are applied
  // client-side so the filters never trigger another request.
  params.set("limit", String(opts?.limit ?? 50));
  try {
    const res = await fetch(
      `${apiUrl("/api/v1/opportunities", base)}?${params.toString()}`,
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as OpportunitiesResponse;
  } catch {
    return null;
  }
}
