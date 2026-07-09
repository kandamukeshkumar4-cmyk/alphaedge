import { API_BASE, ensureApiBase } from "@/lib/alphaedge-api";

/** Live GET /api/v1/arb/opportunities — signal-only, never auto-trades. */
export type ArbOpportunity = {
  id: string;
  pm_market_id: string;
  kalshi_market_id: string;
  pm_title: string;
  kalshi_title: string;
  match_confidence: number;
  theoretical_edge: string;
  gross_spread: string;
  is_arbitrage: boolean;
  stale: boolean;
  signal_only: boolean;
  warning: string;
};

export type ArbOpportunitiesPage = {
  opportunities: ArbOpportunity[];
  total: number;
  fresh_count: number;
  stale_count: number;
  signal_only: boolean;
  note: string;
};

export async function fetchArbOpportunities(
  limit = 10,
): Promise<ArbOpportunitiesPage> {
  const empty: ArbOpportunitiesPage = {
    opportunities: [],
    total: 0,
    fresh_count: 0,
    stale_count: 0,
    signal_only: true,
    note: "These are cross-platform signal observations only.",
  };
  const base = (await ensureApiBase()) || API_BASE;
  if (!base) return empty;
  try {
    const res = await fetch(
      `${base}/api/v1/arb/opportunities?include_stale=true`,
      { cache: "no-store" },
    );
    if (!res.ok) return empty;
    const data = (await res.json()) as ArbOpportunitiesPage;
    const opps = Array.isArray(data.opportunities) ? data.opportunities : [];
    return {
      opportunities: opps.slice(0, limit),
      total: data.total ?? opps.length,
      fresh_count: data.fresh_count ?? 0,
      stale_count: data.stale_count ?? 0,
      signal_only: data.signal_only !== false,
      note: data.note ?? empty.note,
    };
  } catch {
    return empty;
  }
}
