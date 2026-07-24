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

// ---------------------------------------------------------------------------
// Loop V91 SU1 — command-palette client.
//
// FROZEN backend contract (built in parallel — mock fallback mandatory):
//   GET /api/v1/search?q=<str>&limit=20
//     -> {"items":[{slug,title,category,icon,volume,yes_price,hours_to_close}],
//         "total":N,"query":q}
//
// Live-first with an in-memory PAPER mock fallback (same pattern as
// `terminal-api.ts`), so the palette is independently verifiable while the
// backend lands. Unlike `searchUnified` above this client NEVER rejects on
// API failure — it degrades to the mock catalog — but it rethrows aborts so
// the palette can drop stale requests silently. PAPER_TRADING_ONLY: every
// price/volume below is simulated.
// ---------------------------------------------------------------------------

export type SearchMarketItem = {
  slug: string;
  title: string;
  category: string;
  /** Emoji/glyph from the backend; UI renders it in a tile with a fallback. */
  icon: string;
  volume: number;
  /** 0..1 probability price; null when the market has no live YES price. */
  yes_price: number | null;
  hours_to_close: number | null;
};

export type SearchMarketsResponse = {
  items: SearchMarketItem[];
  /** Total matches server-side (may exceed items.length when paginated). */
  total: number;
  query: string;
};

export type SearchApiSource = "live" | "mock";

export type SearchMarketsResult = SearchMarketsResponse & {
  source: SearchApiSource;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function toFiniteNumber(raw: unknown): number | null {
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

/** Tolerant row normalizer — drop anything without a usable slug. */
function normalizeSearchItem(raw: unknown): SearchMarketItem | null {
  const rec = asRecord(raw);
  const slug = typeof rec.slug === "string" ? rec.slug.trim() : "";
  if (!slug) return null;
  const title =
    typeof rec.title === "string" && rec.title.trim() ? rec.title.trim() : slug;
  const rawYes = toFiniteNumber(rec.yes_price);
  const rawVolume = toFiniteNumber(rec.volume);
  const rawHours = toFiniteNumber(rec.hours_to_close);
  return {
    slug,
    title,
    category: typeof rec.category === "string" && rec.category.trim() ? rec.category.trim() : "Market",
    icon: typeof rec.icon === "string" && rec.icon.trim() ? rec.icon.trim() : "📊",
    volume: rawVolume !== null && rawVolume >= 0 ? rawVolume : 0,
    yes_price: rawYes !== null ? Math.min(1, Math.max(0, rawYes)) : null,
    hours_to_close: rawHours !== null && rawHours >= 0 ? rawHours : null,
  };
}

/** Accept the frozen envelope or a bare legacy array of rows. */
function normalizeSearchResponse(raw: unknown, query: string): SearchMarketsResponse {
  const rec = asRecord(raw);
  const rawItems = Array.isArray(raw)
    ? raw
    : Array.isArray(rec.items)
      ? rec.items
      : Array.isArray(rec.results)
        ? rec.results
        : [];
  const items = rawItems
    .map(normalizeSearchItem)
    .filter((item): item is SearchMarketItem => item !== null);
  const total = toFiniteNumber(rec.total);
  return {
    items,
    total: total !== null && total >= 0 ? total : items.length,
    query: typeof rec.query === "string" && rec.query.trim() ? rec.query.trim() : query,
  };
}

/** Seeded PAPER catalog served whenever the live search API is unreachable. */
export const SEARCH_MOCK_CATALOG: readonly SearchMarketItem[] = [
  {
    slug: "nba-2025-01-15-lal-bos",
    title: "Lakers vs Celtics — Jan 15 Tip-Off",
    category: "NBA",
    icon: "🏀",
    volume: 48_200,
    yes_price: 0.52,
    hours_to_close: 6,
  },
  {
    slug: "nba-2025-01-16-nyk-mia",
    title: "Knicks vs Heat — Jan 16",
    category: "NBA",
    icon: "🏀",
    volume: 21_700,
    yes_price: 0.47,
    hours_to_close: 19,
  },
  {
    slug: "nba-2025-01-18-den-okc",
    title: "Nuggets vs Thunder — Jan 18",
    category: "NBA",
    icon: "🏀",
    volume: 33_900,
    yes_price: 0.41,
    hours_to_close: 68,
  },
  {
    slug: "us-2028-dem-nominee-biden-jr",
    title: "Will a sitting governor win the 2028 Democratic nomination?",
    category: "Elections",
    icon: "🗳️",
    volume: 132_400,
    yes_price: 0.23,
    hours_to_close: 2_160,
  },
  {
    slug: "us-2026-senate-az-flip",
    title: "Will Arizona's 2026 Senate seat flip parties?",
    category: "Elections",
    icon: "🗳️",
    volume: 87_300,
    yes_price: 0.38,
    hours_to_close: 3_840,
  },
  {
    slug: "btc-150k-2026-12-31",
    title: "Will Bitcoin close above $150K on Dec 31, 2026?",
    category: "Crypto",
    icon: "₿",
    volume: 214_500,
    yes_price: 0.31,
    hours_to_close: 3_860,
  },
  {
    slug: "eth-btc-ratio-006-2026-09",
    title: "Will ETH/BTC trade above 0.06 before Sep 2026?",
    category: "Crypto",
    icon: "⟠",
    volume: 66_800,
    yes_price: 0.44,
    hours_to_close: 1_440,
  },
  {
    slug: "oscar-2027-best-picture-sequel",
    title: "Will a sequel win Best Picture at the 2027 Oscars?",
    category: "Culture",
    icon: "🎬",
    volume: 12_400,
    yes_price: 0.12,
    hours_to_close: 4_920,
  },
  {
    slug: "fed-cut-sep-2026",
    title: "Will the Fed cut rates at the Sep 2026 meeting?",
    category: "Economics",
    icon: "🏦",
    volume: 158_100,
    yes_price: 0.57,
    hours_to_close: 1_620,
  },
];

/** Case-insensitive all-token match over title + category + slug. */
function mockMatches(item: SearchMarketItem, tokens: string[]): boolean {
  const haystack = `${item.title} ${item.category} ${item.slug}`.toLowerCase();
  return tokens.every((token) => haystack.includes(token));
}

function mockSearch(query: string, limit: number): SearchMarketsResponse {
  const tokens = query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  const matches = SEARCH_MOCK_CATALOG.filter((item) => mockMatches(item, tokens));
  return { items: matches.slice(0, limit), total: matches.length, query };
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

/** Live fetch is capped so a stalled network can never pin the palette. */
export const SEARCH_LIVE_TIMEOUT_MS = 4_000;

/**
 * Command-palette market search (frozen V91 contract). Live-first; on any
 * live failure (network down, non-OK, timeout, legacy shape) falls back to
 * the PAPER mock catalog so the palette always answers. Blank query
 * short-circuits to an empty result without a network call. Caller aborts
 * are rethrown so the palette can drop stale, superseded requests; the
 * internal timeout abort degrades to the mock instead.
 */
export async function searchMarkets(
  q: string,
  limit = 20,
  signal?: AbortSignal,
): Promise<SearchMarketsResult> {
  const query = q.trim();
  if (!query) return { items: [], total: 0, query: "", source: "mock" };

  const clamped = Math.min(50, Math.max(1, Math.floor(limit) || 20));
  const apiBase = await ensureApiBase();
  if (hasLiveApi(apiBase)) {
    const params = new URLSearchParams({ q: query, limit: String(clamped) });
    const internal = new AbortController();
    const onCallerAbort = () => internal.abort();
    signal?.addEventListener("abort", onCallerAbort);
    const timer = setTimeout(() => internal.abort(), SEARCH_LIVE_TIMEOUT_MS);
    try {
      const response = await fetch(`${apiUrl("/api/v1/search", apiBase)}?${params.toString()}`, {
        cache: "no-store",
        signal: internal.signal,
      });
      if (response.ok) {
        const parsed = normalizeSearchResponse(await response.json(), query);
        return { ...parsed, source: "live" };
      }
    } catch (err) {
      if (signal?.aborted && isAbortError(err)) throw err; // stale — caller discards
      // timeout / network failure → fall through to the paper mock
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onCallerAbort);
    }
  }
  return { ...mockSearch(query, clamped), source: "mock" };
}
