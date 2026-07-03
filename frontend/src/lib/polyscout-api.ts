// PolyScout T12 public API client: briefs feed, track record, graded claims,
// latency badges. Read-only, no auth. Every fetcher degrades to empty/null so
// the UI renders gracefully when the backend is down.
import { API_BASE } from "./alphaedge-api";

export type BriefClaim = {
  id: string;
  market_slug: string;
  direction: string;
  horizon_minutes: number;
  confidence: number;
  price_at_claim: number | null;
  status: string; // pending | correct | incorrect | void
  resolution_price: number | null;
  resolved_at: string | null;
  created_at: string;
};

export type AnalystBrief = {
  id: string;
  market_slug: string;
  headline: string;
  body_markdown: string;
  citations: Array<{ kind?: string; label?: string; ref?: string; [k: string]: unknown }>;
  model_version: string;
  prompt_version: string;
  generator: string; // llm | fallback
  kind: string; // brief | digest
  persona?: string | null; // E13 analyst lens: macro | whale-flow | news
  latency_ms: number;
  created_at: string;
  claim: BriefClaim | null;
};

export type BriefsPage = {
  items: AnalystBrief[];
  total: number;
  limit: number;
  offset: number;
};

export type TrackRecordRow = {
  dimension: string;
  dim_key: string;
  window_days: number;
  n: number;
  accuracy: number;
  brier: number;
  provisional: boolean;
};

export type LatencyBadge = {
  slug: string;
  last_tick_at: string | null;
  age_seconds: number | null;
  freshness: "live" | "delayed" | "stale";
};

async function getJson<T>(path: string): Promise<T | null> {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchBriefs(opts?: {
  market?: string;
  category?: string;
  kind?: string;
  limit?: number;
  offset?: number;
}): Promise<BriefsPage> {
  const params = new URLSearchParams();
  if (opts?.market) params.set("market", opts.market);
  if (opts?.category) params.set("category", opts.category);
  if (opts?.kind) params.set("kind", opts.kind);
  params.set("limit", String(opts?.limit ?? 20));
  params.set("offset", String(opts?.offset ?? 0));
  const data = await getJson<BriefsPage | AnalystBrief[]>(`/api/v1/briefs?${params}`);
  if (!data) return { items: [], total: 0, limit: opts?.limit ?? 20, offset: opts?.offset ?? 0 };
  if (Array.isArray(data)) {
    return { items: data, total: data.length, limit: opts?.limit ?? 20, offset: opts?.offset ?? 0 };
  }
  return { items: data.items ?? [], total: data.total ?? 0, limit: data.limit, offset: data.offset };
}

export async function fetchBrief(id: string): Promise<AnalystBrief | null> {
  return getJson<AnalystBrief>(`/api/v1/briefs/${encodeURIComponent(id)}`);
}

export async function fetchTrackRecord(): Promise<TrackRecordRow[]> {
  const data = await getJson<
    TrackRecordRow[] | { items?: TrackRecordRow[]; aggregates?: TrackRecordRow[] }
  >("/api/v1/analyst/track-record");
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.aggregates ?? data.items ?? [];
}

export async function fetchGradedClaims(opts?: {
  limit?: number;
  offset?: number;
}): Promise<BriefClaim[]> {
  const params = new URLSearchParams();
  params.set("limit", String(opts?.limit ?? 50));
  params.set("offset", String(opts?.offset ?? 0));
  const data = await getJson<BriefClaim[] | { items?: BriefClaim[] }>(
    `/api/v1/analyst/track-record/claims?${params}`,
  );
  if (!data) return [];
  return Array.isArray(data) ? data : (data.items ?? []);
}

export async function fetchLatency(slug: string): Promise<LatencyBadge | null> {
  const data = await getJson<{
    slug?: string;
    last_tick_at?: string | null;
    age_seconds?: number | null;
    freshness?: string;
  }>(`/api/v1/markets/${encodeURIComponent(slug)}/latency`);
  if (!data) return null;
  return {
    slug: data.slug ?? slug,
    last_tick_at: data.last_tick_at ?? null,
    age_seconds: data.age_seconds ?? null,
    freshness: latencyState(data.age_seconds ?? null, data.freshness),
  };
}

export function latencyState(
  ageSeconds: number | null,
  serverState?: string,
): "live" | "delayed" | "stale" {
  if (serverState === "live" || serverState === "delayed" || serverState === "stale") {
    return serverState;
  }
  if (ageSeconds == null) return "stale";
  if (ageSeconds < 60) return "live";
  if (ageSeconds < 600) return "delayed";
  return "stale";
}
