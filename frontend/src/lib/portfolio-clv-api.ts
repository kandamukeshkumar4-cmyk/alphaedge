import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * X02: portfolio CLV summary — GET /api/v1/portfolio/clv-summary (backend K02).
 * AUTHED (JWT — 401 when anonymous). Realized closing-line-value distribution
 * for the caller's SETTLED paper orders: count, mean, positive_share, total, and
 * a fixed-bin histogram. Read-only, paper trading only — nothing is placed.
 *
 * Honest empties: `source:"none"` (no settled orders) vs `source:"paper_orders"`
 * with count 0 (settled orders but none matched a resolved closing line). The
 * view model surfaces both without fabricating a distribution.
 * See goals/loop-v6/API-NOTES.md → K02.
 */

export type ClvHistogramBin = {
  label: string;
  lo: number | null;
  hi: number | null;
  count: number;
};

export type PortfolioClvSummary = {
  count: number;
  mean: number | null;
  positive_share: number | null;
  total_clv: number;
  histogram: ClvHistogramBin[];
  matched_slugs: number;
  settled_orders: number;
  source: string;
  paper_trading_only: boolean;
  disclaimer: string;
};

// ---------------------------------------------------------------------------
// View model (pure — unit-tested)
// ---------------------------------------------------------------------------

export type ClvBarView = {
  label: string;
  count: number;
  /** 0–1 height fraction relative to the fullest bin. */
  fraction: number;
  tone: "up" | "down" | "neutral";
};

export type ClvSummaryView = {
  /** False when the response is null (unreachable / 401). */
  reachable: boolean;
  /** True only when there is a real distribution (count > 0). */
  available: boolean;
  /** Honest empty explanation when reachable but count 0. */
  emptyMessage: string | null;
  count: number;
  countLabel: string;
  /** Realized-CLV mean as a fraction (for AnimatedNumber); null when empty. */
  meanValue: number | null;
  meanLabel: string;
  meanTone: "up" | "down" | "neutral";
  /** Positive share as a fraction 0–1 (for AnimatedNumber); null when empty. */
  positiveShareValue: number | null;
  positiveShareLabel: string;
  totalClvLabel: string;
  totalClvTone: "up" | "down" | "neutral";
  bars: ClvBarView[];
  settledOrders: number;
  matchedSlugs: number;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Realized closing-line value on SETTLED paper trades only. Research signal — simulated funds, no execution. Not financial advice.";

// Fixed bins mirror the backend order; anything at/above 0 is a "win" tone.
const BIN_TONE: Record<string, "up" | "down" | "neutral"> = {
  "<= -0.10": "down",
  "-0.10..-0.05": "down",
  "-0.05..0.00": "down",
  "0.00..0.05": "up",
  "0.05..0.10": "up",
  ">= 0.10": "up",
};

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function signedPts(v: number): string {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)} pts`;
}

function tone(v: number | null): "up" | "down" | "neutral" {
  if (v === null || Math.abs(v) < 1e-9) return "neutral";
  return v > 0 ? "up" : "down";
}

function emptyView(
  reachable: boolean,
  emptyMessage: string | null,
  disclaimer: string,
  settledOrders = 0,
  matchedSlugs = 0,
): ClvSummaryView {
  return {
    reachable,
    available: false,
    emptyMessage,
    count: 0,
    countLabel: "0",
    meanValue: null,
    meanLabel: "—",
    meanTone: "neutral",
    positiveShareValue: null,
    positiveShareLabel: "—",
    totalClvLabel: "—",
    totalClvTone: "neutral",
    bars: [],
    settledOrders,
    matchedSlugs,
    disclaimer,
  };
}

/** Pure transform: raw K02 response → view model. Honest empties, no fabrication. */
export function buildClvSummaryView(raw: PortfolioClvSummary | null): ClvSummaryView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) return emptyView(false, null, disclaimer);

  const count = isFiniteNum(raw.count) ? raw.count : 0;
  if (count <= 0) {
    const settled = isFiniteNum(raw.settled_orders) ? raw.settled_orders : 0;
    const message =
      raw.source === "none" || settled === 0
        ? "No settled paper trades yet — your realized CLV appears here once markets you traded resolve."
        : "You have settled paper trades, but none of their markets have a resolved closing line yet, so no CLV can be scored. Nothing is fabricated.";
    return emptyView(true, message, disclaimer, settled, 0);
  }

  const bins = Array.isArray(raw.histogram) ? raw.histogram : [];
  const maxBin = bins.reduce((m, b) => Math.max(m, isFiniteNum(b.count) ? b.count : 0), 0);
  const bars: ClvBarView[] = bins.map((b) => {
    const c = isFiniteNum(b.count) ? b.count : 0;
    return {
      label: b.label,
      count: c,
      fraction: maxBin > 0 ? c / maxBin : 0,
      tone: BIN_TONE[b.label] ?? "neutral",
    };
  });

  const mean = isFiniteNum(raw.mean) ? raw.mean : null;
  const posShare = isFiniteNum(raw.positive_share) ? raw.positive_share : null;
  const total = isFiniteNum(raw.total_clv) ? raw.total_clv : 0;

  return {
    reachable: true,
    available: true,
    emptyMessage: null,
    count,
    countLabel: String(count),
    meanValue: mean,
    meanLabel: mean === null ? "—" : signedPts(mean),
    meanTone: tone(mean),
    positiveShareValue: posShare,
    positiveShareLabel: posShare === null ? "—" : `${Math.round(posShare * 100)}%`,
    totalClvLabel: signedPts(total),
    totalClvTone: tone(total),
    bars,
    settledOrders: isFiniteNum(raw.settled_orders) ? raw.settled_orders : count,
    matchedSlugs: isFiniteNum(raw.matched_slugs) ? raw.matched_slugs : 0,
    disclaimer,
  };
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

/**
 * Fetch the caller's realized CLV summary. Requires a JWT (returns null when no
 * token / no live API / on error). A null result means "unreachable or 401" —
 * the caller shows the anon/sign-in state; an honest empty distribution comes
 * back as a real response with count 0.
 */
export async function fetchPortfolioClvSummary(
  token: string | null,
  signal?: AbortSignal,
): Promise<PortfolioClvSummary | null> {
  if (!token) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/portfolio/clv-summary", base), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as PortfolioClvSummary;
  } catch {
    return null;
  }
}
