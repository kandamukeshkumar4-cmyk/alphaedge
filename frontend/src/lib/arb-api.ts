import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/** One venue leg of a matched arb observation (G02 additive field). */
export type ArbLeg = {
  platform: string;
  market_id: string;
  outcome: string;
  price: string; // backend serialises price/fee as strings
  fee: string;
};

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
  // G02 additive optional fields (default-safe for older responses).
  confidence: number | null;
  spread_bps: number;
  legs: ArbLeg[];
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
  // Empty base is valid in browser prod (same-origin Vercel → HF rewrite).
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return empty;
  try {
    const res = await fetch(
      apiUrl("/api/v1/arb/opportunities?include_stale=true", base),
      { cache: "no-store" },
    );
    if (!res.ok) return empty;
    const data = (await res.json()) as ArbOpportunitiesPage;
    const opps = (Array.isArray(data.opportunities) ? data.opportunities : []).map((o) => ({
      ...o,
      confidence: o.confidence ?? null,
      spread_bps: o.spread_bps ?? 0,
      legs: Array.isArray(o.legs) ? o.legs : [],
    }));
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
