/**
 * Loop 98 (MU1) — Marketplace maturity typed client.
 *
 * LIVE backend contracts:
 *   POST /api/v1/skills/{id}/rate    {stars:1-5} -> {avg,count,my_stars}
 *   POST /api/v1/scanners/{id}/rate  {stars:1-5} -> {avg,count,my_stars}
 *   GET  /api/v1/skills/trending?limit    -> {items:[+avg_rating,rating_count,trending_score]}
 *   GET  /api/v1/scanners/trending?limit  -> {items:[+avg_rating,rating_count,trending_score]}
 *   GET  /api/v1/skills/featured          -> {items}
 *   GET  /api/v1/scanners/featured        -> {items}
 *
 * Live first (Bearer token like the other authed clients); on any failure the
 * caller gets an in-memory PAPER mock so ratings / trending / featured work
 * while the backend is offline. Mirrors skills-api.ts: all fetch wiring
 * lives here — UI components never call fetch.
 *
 * PAPER_TRADING_ONLY — rating / browsing never touch the order path.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MarketplaceKind = "skill" | "scanner";

export type ApiSource = "live" | "mock";

export type RatingOut = {
  avg: number;
  count: number;
  my_stars: number;
};

export type MarketplaceCard = {
  kind: MarketplaceKind;
  id: string;
  name: string;
  description: string;
  icon: string;
  run_count: number;
  is_featured: boolean;
};

export type TrendingItem = MarketplaceCard & {
  avg_rating: number;
  rating_count: number;
  trending_score: number;
};

export type FeaturedItem = MarketplaceCard;

export type RateResult = {
  rating: RatingOut;
  source: ApiSource;
};

export type TrendingResult = {
  items: TrendingItem[];
  source: ApiSource;
};

export type FeaturedResult = {
  items: FeaturedItem[];
  source: ApiSource;
};

// ---------------------------------------------------------------------------
// Payload guards + normalizers
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clampStars(stars: number): number {
  const n = Math.round(stars);
  if (n < 1) return 1;
  if (n > 5) return 5;
  return n;
}


function normalizeRating(raw: unknown): RatingOut | null {
  const rec = asRecord(raw);
  const avg = asNumber(rec.avg, NaN);
  const count = asNumber(rec.count, NaN);
  const myStars = asNumber(rec.my_stars ?? rec.myStars, NaN);
  if (!Number.isFinite(avg) || !Number.isFinite(count) || !Number.isFinite(myStars)) {
    return null;
  }
  return { avg, count: Math.max(0, Math.floor(count)), my_stars: clampStars(myStars) };
}

function normalizeCard(
  kind: MarketplaceKind,
  raw: unknown,
): MarketplaceCard | null {
  const rec = asRecord(raw);
  if (typeof rec.id !== "string" && typeof rec.name !== "string") return null;
  const id = typeof rec.id === "string" ? rec.id : String(rec.name).toLowerCase();
  const runCount = asNumber(rec.run_count ?? rec.runCount, 0);
  return {
    kind,
    id,
    name: typeof rec.name === "string" ? rec.name : id,
    description: typeof rec.description === "string" ? rec.description : "",
    icon:
      typeof rec.icon === "string" && rec.icon
        ? rec.icon
        : kind === "scanner"
          ? "📡"
          : "✦",
    run_count: Math.max(0, Math.floor(runCount)),
    is_featured: rec.is_featured === true || rec.isFeatured === true,
  };
}

function normalizeTrending(
  kind: MarketplaceKind,
  raw: unknown,
): TrendingItem | null {
  const card = normalizeCard(kind, raw);
  if (!card) return null;
  const rec = asRecord(raw);
  const avg = asNumber(rec.avg_rating ?? rec.avgRating, 0);
  const count = asNumber(rec.rating_count ?? rec.ratingCount, 0);
  const score = asNumber(rec.trending_score ?? rec.trendingScore, avg);
  return {
    ...card,
    avg_rating: avg,
    rating_count: Math.max(0, Math.floor(count)),
    trending_score: score,
  };
}

function asItemList(live: unknown): unknown[] {
  if (Array.isArray(live)) return live;
  const rec = asRecord(live);
  if (Array.isArray(rec.items)) return rec.items as unknown[];
  return [];
}

// ---------------------------------------------------------------------------
// Mock store
// ---------------------------------------------------------------------------

type MockRatingState = {
  sum: number;
  count: number;
  my_stars: number;
};

type MockCatalogEntry = MarketplaceCard & {
  /** Proxy for recent runs used in trending_score. */
  recent_runs: number;
};

const MOCK_CATALOG: MockCatalogEntry[] = [
  {
    kind: "skill",
    id: "confluence",
    name: "Full confluence scan",
    description: "Price, whale, news, sentiment, model — one paper verdict.",
    icon: "🎯",
    run_count: 128,
    recent_runs: 42,
    is_featured: true,
  },
  {
    kind: "skill",
    id: "whale",
    name: "Whale flow digest",
    description: "Large simulated flow on the board, summarized.",
    icon: "🐋",
    run_count: 64,
    recent_runs: 28,
    is_featured: true,
  },
  {
    kind: "skill",
    id: "price",
    name: "Pre-game price read",
    description: "Candles and drift into tip-off, in one card.",
    icon: "📈",
    run_count: 41,
    recent_runs: 11,
    is_featured: false,
  },
  {
    kind: "scanner",
    id: "scn-mock-whale",
    name: "NBA whale + trend confluence",
    description: "Whale flow and price trend on NBA markets every 15 minutes.",
    icon: "📡",
    run_count: 56,
    recent_runs: 31,
    is_featured: true,
  },
  {
    kind: "scanner",
    id: "scn-mock-daily",
    name: "Daily model edge sweep",
    description: "Model vs market gap across categories once a day.",
    icon: "📡",
    run_count: 22,
    recent_runs: 9,
    is_featured: false,
  },
];

/** Weight matches backend marketplace_trending_service.RECENT_WEIGHT. */
const RECENT_WEIGHT = 0.1;

const DEFAULT_RATINGS: Record<string, MockRatingState> = {
  "skill:confluence": { sum: 22, count: 5, my_stars: 0 },
  "skill:whale": { sum: 14, count: 4, my_stars: 0 },
  "skill:price": { sum: 7, count: 2, my_stars: 0 },
  "scanner:scn-mock-whale": { sum: 18, count: 4, my_stars: 0 },
  "scanner:scn-mock-daily": { sum: 8, count: 2, my_stars: 0 },
};

let mockCatalog: MockCatalogEntry[] = MOCK_CATALOG.map((e) => ({ ...e }));
let mockRatings: Record<string, MockRatingState> = { ...DEFAULT_RATINGS };

function ratingKey(kind: MarketplaceKind, id: string): string {
  return `${kind}:${id}`;
}

function mockAvg(state: MockRatingState | undefined): number {
  if (!state || state.count <= 0) return 0;
  return state.sum / state.count;
}

function ensureMockRating(kind: MarketplaceKind, id: string): MockRatingState {
  const key = ratingKey(kind, id);
  const existing = mockRatings[key];
  if (existing) return existing;
  const fresh: MockRatingState = { sum: 0, count: 0, my_stars: 0 };
  mockRatings[key] = fresh;
  return fresh;
}

function mockRate(
  kind: MarketplaceKind,
  id: string,
  stars: number,
): RatingOut {
  const clamped = clampStars(stars);
  const state = ensureMockRating(kind, id);
  if (state.my_stars > 0) {
    state.sum = state.sum - state.my_stars + clamped;
  } else {
    state.sum += clamped;
    state.count += 1;
  }
  state.my_stars = clamped;
  return {
    avg: mockAvg(state),
    count: state.count,
    my_stars: state.my_stars,
  };
}

function mockTrending(kind: MarketplaceKind, limit: number): TrendingItem[] {
  const items = mockCatalog
    .filter((e) => e.kind === kind)
    .map((e) => {
      const state = mockRatings[ratingKey(kind, e.id)];
      const avg = mockAvg(state);
      const count = state?.count ?? 0;
      const score = e.recent_runs * RECENT_WEIGHT + avg;
      return {
        kind: e.kind,
        id: e.id,
        name: e.name,
        description: e.description,
        icon: e.icon,
        run_count: e.run_count,
        is_featured: e.is_featured,
        avg_rating: avg,
        rating_count: count,
        trending_score: score,
      } satisfies TrendingItem;
    })
    .sort((a, b) => b.trending_score - a.trending_score);
  return items.slice(0, Math.max(0, limit));
}

function mockFeatured(kind: MarketplaceKind): FeaturedItem[] {
  return mockCatalog
    .filter((e) => e.kind === kind && e.is_featured)
    .map((e) => ({
      kind: e.kind,
      id: e.id,
      name: e.name,
      description: e.description,
      icon: e.icon,
      run_count: e.run_count,
      is_featured: true,
    }));
}

/** Test / wiring hook — reset the in-memory marketplace mock. */
export function resetMarketplaceMockStore(): void {
  mockCatalog = MOCK_CATALOG.map((e) => ({ ...e }));
  mockRatings = Object.fromEntries(
    Object.entries(DEFAULT_RATINGS).map(([k, v]) => [k, { ...v }]),
  );
}

// ---------------------------------------------------------------------------
// Fetch layer
// ---------------------------------------------------------------------------

type MarketplaceFetch = typeof fetch;

let marketplaceFetch: MarketplaceFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setMarketplaceFetch(fn: MarketplaceFetch): void {
  marketplaceFetch = fn;
}

async function liveBase(): Promise<string | null> {
  const base = (await ensureApiBase()) || undefined;
  return base && hasLiveApi(base) ? base : null;
}

async function tryLiveJson(
  path: string,
  token: string | null,
  init?: RequestInit,
): Promise<unknown | null> {
  const base = await liveBase();
  if (!base) return null;
  try {
    const res = await marketplaceFetch(apiUrl(path, base), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function kindPath(kind: MarketplaceKind): "skills" | "scanners" {
  return kind === "skill" ? "skills" : "scanners";
}

// ---------------------------------------------------------------------------
// Endpoints — live first, mock fallback. None of these reject.
// ---------------------------------------------------------------------------

/** POST rate for a skill. Never rejects. */
export async function rateSkill(
  id: string,
  stars: number,
  token: string | null = null,
): Promise<RateResult> {
  return rate("skill", id, stars, token);
}

/** POST rate for a scanner. Never rejects. */
export async function rateScanner(
  id: string,
  stars: number,
  token: string | null = null,
): Promise<RateResult> {
  return rate("scanner", id, stars, token);
}

/** POST rate for skill or scanner. Never rejects. */
export async function rate(
  kind: MarketplaceKind,
  id: string,
  stars: number,
  token: string | null = null,
): Promise<RateResult> {
  const clamped = clampStars(stars);
  const live = await tryLiveJson(
    `/api/v1/${kindPath(kind)}/${encodeURIComponent(id)}/rate`,
    token,
    { method: "POST", body: JSON.stringify({ stars: clamped }) },
  );
  const rating = live ? normalizeRating(live) : null;
  if (rating) return { rating, source: "live" };
  return { rating: mockRate(kind, id, clamped), source: "mock" };
}

/** GET trending skills, sorted by trending_score desc. Never rejects. */
export async function getTrendingSkills(
  limit = 10,
  token: string | null = null,
): Promise<TrendingResult> {
  return getTrending("skill", limit, token);
}

/** GET trending scanners, sorted by trending_score desc. Never rejects. */
export async function getTrendingScanners(
  limit = 10,
  token: string | null = null,
): Promise<TrendingResult> {
  return getTrending("scanner", limit, token);
}

/** GET trending for skill or scanner. Never rejects. */
export async function getTrending(
  kind: MarketplaceKind,
  limit = 10,
  token: string | null = null,
): Promise<TrendingResult> {
  const capped = Math.max(1, Math.min(50, Math.floor(limit) || 10));
  const live = await tryLiveJson(
    `/api/v1/${kindPath(kind)}/trending?limit=${capped}`,
    token,
  );
  if (live) {
    const items = asItemList(live)
      .map((raw) => normalizeTrending(kind, raw))
      .filter((t): t is TrendingItem => t !== null)
      .sort((a, b) => b.trending_score - a.trending_score)
      .slice(0, capped);
    if (items.length > 0) return { items, source: "live" };
  }
  return { items: mockTrending(kind, capped), source: "mock" };
}

/** GET featured skills. Never rejects. */
export async function getFeaturedSkills(
  token: string | null = null,
): Promise<FeaturedResult> {
  return getFeatured("skill", token);
}

/** GET featured scanners. Never rejects. */
export async function getFeaturedScanners(
  token: string | null = null,
): Promise<FeaturedResult> {
  return getFeatured("scanner", token);
}

/** GET featured for skill or scanner. Never rejects. */
export async function getFeatured(
  kind: MarketplaceKind,
  token: string | null = null,
): Promise<FeaturedResult> {
  const live = await tryLiveJson(`/api/v1/${kindPath(kind)}/featured`, token);
  if (live) {
    const items = asItemList(live)
      .map((raw) => normalizeCard(kind, raw))
      .filter((t): t is FeaturedItem => t !== null)
      .map((t) => ({ ...t, is_featured: true }));
    if (items.length > 0) return { items, source: "live" };
  }
  return { items: mockFeatured(kind), source: "mock" };
}

/**
 * Combined trending (skills + scanners), sorted by trending_score.
 * Used by /library Trending row.
 */
export async function getTrendingMarketplace(
  limit = 8,
  token: string | null = null,
): Promise<TrendingResult> {
  const capped = Math.max(1, Math.min(50, Math.floor(limit) || 8));
  const [skills, scanners] = await Promise.all([
    getTrending("skill", capped, token),
    getTrending("scanner", capped, token),
  ]);
  const source: ApiSource =
    skills.source === "live" || scanners.source === "live" ? "live" : "mock";
  const items = [...skills.items, ...scanners.items]
    .sort((a, b) => b.trending_score - a.trending_score)
    .slice(0, capped);
  return { items, source };
}

/**
 * Combined featured (skills + scanners). Used by /library Featured row.
 */
export async function getFeaturedMarketplace(
  token: string | null = null,
): Promise<FeaturedResult> {
  const [skills, scanners] = await Promise.all([
    getFeatured("skill", token),
    getFeatured("scanner", token),
  ]);
  const source: ApiSource =
    skills.source === "live" || scanners.source === "live" ? "live" : "mock";
  return { items: [...skills.items, ...scanners.items], source };
}

