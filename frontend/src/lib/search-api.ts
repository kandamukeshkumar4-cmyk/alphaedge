import { apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

/** Row shape of GET /api/v1/search (backend U01 UnifiedMarketSearchResult). */
export type UnifiedSearchResult = {
  slug: string;
  title: string;
  platform: string;
  category: string;
  market_type: string;
  yes_price: number | null;
  volume: number;
  status: string;
};

/**
 * Unified cross-platform market search. Returns [] without a network call
 * when the query is blank or no live API is configured; throws on HTTP
 * errors so the caller can render an honest error state.
 */
export async function searchUnified(
  q: string,
  limit = 8,
  signal?: AbortSignal,
): Promise<UnifiedSearchResult[]> {
  const query = q.trim();
  if (!query) return [];

  const apiBase = await ensureApiBase();
  if (!hasLiveApi(apiBase)) return [];

  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const href = `${apiUrl("/api/v1/search", apiBase)}?${params.toString()}`;
  const response = await fetch(href, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(`Search HTTP ${response.status}`);
  }
  return (await response.json()) as UnifiedSearchResult[];
}
