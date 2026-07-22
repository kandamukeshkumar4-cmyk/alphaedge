/**
 * Loop V85 (L1) — Screener typed client.
 *
 * Backend contract (D-U1, built in parallel):
 *   GET /api/v1/screener?category=&min_volume=&min_edge=&max_hours_to_close=
 *                          &sort=&limit=
 *     → { "items": ScreenerItem[], "total": number }
 *   ScreenerItem: { slug, title, category, icon, volume, yes_price,
 *                   move_24h, model_edge, hours_to_close }
 *
 * The live API is attempted first (same-origin / Vercel rewrite → HF Space,
 * resolved via `ensureApiBase`/`hasLiveApi` like the other clients); on any
 * failure the caller gets an in-memory PAPER mock so the screener renders while
 * the backend is offline. Mirrors `terminal-api.ts` (Loop V79): all fetch
 * wiring lives here — UI components never call `fetch`.
 *
 * PAPER_TRADING_ONLY — the screener is read-only research: it surfaces paper
 * markets and never touches the order path.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

// ---------------------------------------------------------------------------
// Types (backend contract)
// ---------------------------------------------------------------------------

export type ScreenerCategory = "nba" | "election" | "crypto" | "sports" | "culture";

export type ScreenerSort = "edge" | "volume" | "move" | "closing";

export type ScreenerItem = {
  slug: string;
  title: string;
  category: string;
  icon: string;
  volume: number;
  yes_price: number;
  /** 24h price delta as a signed fraction (e.g. 0.032 = +3.2%). */
  move_24h: number;
  /** Model probability minus market implied (signed fraction). */
  model_edge: number;
  /** Hours until market close (null when already closed / unknown). */
  hours_to_close: number | null;
};

export type ScreenerResult = {
  items: ScreenerItem[];
  total: number;
};

export type ScreenerFilters = {
  category?: string;
  min_volume?: number;
  min_edge?: number;
  max_hours_to_close?: number;
  sort?: ScreenerSort;
  limit?: number;
};

export type ApiSource = "live" | "mock";

// ---------------------------------------------------------------------------
// Payload guards + normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asNullableNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function normalizeItem(raw: unknown): ScreenerItem | null {
  const rec = asRecord(raw);
  if (typeof rec.slug !== "string" || !rec.slug) return null;
  const hours = asNullableNumber(rec.hours_to_close);
  return {
    slug: rec.slug,
    title: typeof rec.title === "string" && rec.title ? rec.title : rec.slug,
    category: typeof rec.category === "string" && rec.category ? rec.category : "sports",
    icon: typeof rec.icon === "string" && rec.icon ? rec.icon : "📊",
    volume: Math.max(0, asNumber(rec.volume)),
    yes_price: clampProb(asNumber(rec.yes_price, 0.5)),
    move_24h: asNumber(rec.move_24h),
    model_edge: asNumber(rec.model_edge),
    hours_to_close: hours === null ? null : Math.max(0, hours),
  };
}

function clampProb(p: number): number {
  if (!Number.isFinite(p)) return 0.5;
  if (p < 0) return 0;
  if (p > 1) return 1;
  return p;
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live screener API is absent)
// ---------------------------------------------------------------------------

const MOCK_ITEMS: ScreenerItem[] = [
  {
    slug: "nba-2025-01-15-lal-bos",
    title: "Lakers vs Celtics — Jan 15",
    category: "nba",
    icon: "🏀",
    volume: 2_413_000,
    yes_price: 0.64,
    move_24h: 0.018,
    model_edge: 0.041,
    hours_to_close: 6.5,
  },
  {
    slug: "nba-2025-01-16-gsw-den",
    title: "Warriors vs Nuggets — Jan 16",
    category: "nba",
    icon: "🏀",
    volume: 986_500,
    yes_price: 0.51,
    move_24h: -0.012,
    model_edge: 0.008,
    hours_to_close: 28,
  },
  {
    slug: "nba-2025-01-16-mil-mia",
    title: "Bucks vs Heat — Jan 16",
    category: "nba",
    icon: "🏀",
    volume: 742_000,
    yes_price: 0.47,
    move_24h: 0.024,
    model_edge: -0.015,
    hours_to_close: 30,
  },
  {
    slug: "election-2026-senate-oh",
    title: "Ohio Senate 2026 winner",
    category: "election",
    icon: "🗳️",
    volume: 1_180_000,
    yes_price: 0.58,
    move_24h: 0.005,
    model_edge: 0.022,
    hours_to_close: 220,
  },
  {
    slug: "election-2026-gov-ca",
    title: "California Governor 2026",
    category: "election",
    icon: "🗳️",
    volume: 640_000,
    yes_price: 0.71,
    move_24h: -0.008,
    model_edge: -0.031,
    hours_to_close: 540,
  },
  {
    slug: "crypto-btc-150k-2026",
    title: "BTC above $150k in 2026?",
    category: "crypto",
    icon: "₿",
    volume: 3_050_000,
    yes_price: 0.39,
    move_24h: 0.061,
    model_edge: 0.053,
    hours_to_close: 720,
  },
  {
    slug: "crypto-eth-5k-2026",
    title: "ETH above $5k by Q3 2026?",
    category: "crypto",
    icon: "Ξ",
    volume: 512_000,
    yes_price: 0.22,
    move_24h: -0.044,
    model_edge: -0.019,
    hours_to_close: 960,
  },
  {
    slug: "culture-oscar-best-pic",
    title: "Oscar Best Picture 2026 winner",
    category: "culture",
    icon: "🏆",
    volume: 318_000,
    yes_price: 0.45,
    move_24h: 0.002,
    model_edge: 0.011,
    hours_to_close: 1200,
  },
];

let mockItems: ScreenerItem[] = MOCK_ITEMS.map((i) => ({ ...i }));

/** Test / wiring hook — reset the in-memory mock screener rows. */
export function resetScreenerMockStore(): void {
  mockItems = MOCK_ITEMS.map((i) => ({ ...i }));
}

// ---------------------------------------------------------------------------
// Derived helpers (pure) — UI formatting without components doing the math
// ---------------------------------------------------------------------------

/** Sort a copy of items per the requested axis (stable, deterministic). */
export function sortItems(
  items: ScreenerItem[],
  sort: ScreenerSort | undefined,
): ScreenerItem[] {
  const absEdge = (i: ScreenerItem) => Math.abs(i.model_edge);
  switch (sort) {
    case "volume":
      return [...items].sort((a, b) => b.volume - a.volume);
    case "move":
      return [...items].sort((a, b) => Math.abs(b.move_24h) - Math.abs(a.move_24h));
    case "closing":
      return [...items].sort((a, b) => {
        const ah = a.hours_to_close ?? Number.POSITIVE_INFINITY;
        const bh = b.hours_to_close ?? Number.POSITIVE_INFINITY;
        return ah - bh;
      });
    case "edge":
    default:
      // Default to edge: largest |edge| first — the screener's whole point.
      return [...items].sort((a, b) => absEdge(b) - absEdge(a));
  }
}

/**
 * Apply filter + sort + limit purely on the mock store (mirrors backend
 * query handling so the mock path matches live semantics).
 */
function applyFilters(filters: ScreenerFilters): ScreenerResult {
  let items = mockItems.map((i) => ({ ...i }));
  const category = filters.category?.trim().toLowerCase();
  if (category && category !== "all") {
    items = items.filter((i) => i.category.toLowerCase() === category);
  }
  if (typeof filters.min_volume === "number" && Number.isFinite(filters.min_volume)) {
    items = items.filter((i) => i.volume >= (filters.min_volume as number));
  }
  if (typeof filters.min_edge === "number" && Number.isFinite(filters.min_edge)) {
    items = items.filter((i) => Math.abs(i.model_edge) >= (filters.min_edge as number));
  }
  if (
    typeof filters.max_hours_to_close === "number" &&
    Number.isFinite(filters.max_hours_to_close)
  ) {
    items = items.filter(
      (i) => i.hours_to_close !== null && i.hours_to_close <= (filters.max_hours_to_close as number),
    );
  }
  items = sortItems(items, filters.sort);
  const total = items.length;
  const limit = typeof filters.limit === "number" && filters.limit > 0 ? filters.limit : 50;
  return { items: items.slice(0, limit), total };
}

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the screener API)
// ---------------------------------------------------------------------------

// ── Pure format helpers (UI rendering without components doing the math) ──

/** "$2.4M" / "$986k" / "$320" — compact USD volume. */
export function formatVolume(volume: number): string {
  if (!Number.isFinite(volume) || volume <= 0) return "—";
  if (volume >= 1_000_000) return `$${(volume / 1_000_000).toFixed(1)}M`;
  if (volume >= 1_000) return `$${Math.round(volume / 1000)}k`;
  return `$${Math.round(volume)}`;
}

/** "64¢" price label from a 0–1 probability. */
export function formatPrice(prob: number): string {
  if (!Number.isFinite(prob)) return "—";
  const cents = Math.round(prob * 100);
  return `${cents}¢`;
}

/** Signed percent from a fraction: +3.2% / -1.2%. */
export function formatPercent(fraction: number, digits = 1): string {
  if (!Number.isFinite(fraction)) return "—";
  const sign = fraction > 0 ? "+" : "";
  return `${sign}${(fraction * 100).toFixed(digits)}%`;
}

/** "6.5h" / "2.0d" / "—" for hours-to-close (null = closed/unknown). */
export function formatHours(hours: number | null): string {
  if (hours === null || !Number.isFinite(hours)) return "—";
  if (hours >= 48) return `${(hours / 24).toFixed(1)}d`;
  if (hours >= 1) return `${hours.toFixed(1)}h`;
  return "<1h";
}

type ScreenerFetch = typeof fetch;

let screenerFetch: ScreenerFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setScreenerFetch(fn: ScreenerFetch): void {
  screenerFetch = fn;
}

async function liveBase(): Promise<string | null> {
  const base = (await ensureApiBase()) || undefined;
  return base && hasLiveApi(base) ? base : null;
}

function buildQuery(filters: ScreenerFilters): string {
  const params = new URLSearchParams();
  if (filters.category && filters.category !== "all") {
    params.set("category", filters.category);
  }
  if (typeof filters.min_volume === "number" && Number.isFinite(filters.min_volume)) {
    params.set("min_volume", String(filters.min_volume));
  }
  if (typeof filters.min_edge === "number" && Number.isFinite(filters.min_edge)) {
    params.set("min_edge", String(filters.min_edge));
  }
  if (
    typeof filters.max_hours_to_close === "number" &&
    Number.isFinite(filters.max_hours_to_close)
  ) {
    params.set("max_hours_to_close", String(filters.max_hours_to_close));
  }
  if (filters.sort) params.set("sort", filters.sort);
  if (typeof filters.limit === "number" && filters.limit > 0) {
    params.set("limit", String(filters.limit));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

/**
 * List screener rows. Live first, mock fallback. Never rejects.
 * Token is optional — the GET screener endpoint is unauthenticated, but we
 * pass it when available for parity with the other authed clients.
 */
export async function listScreener(
  filters: ScreenerFilters = {},
  token: string | null = null,
): Promise<{ result: ScreenerResult; source: ApiSource }> {
  const base = await liveBase();
  if (base) {
    try {
      const res = await screenerFetch(apiUrl(`/api/v1/screener${buildQuery(filters)}`, base), {
        headers: {
          Accept: "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        cache: "no-store",
      });
      if (res.ok) {
        const data = (await res.json()) as unknown;
        const rec = asRecord(data);
        const rawItems = Array.isArray(rec.items) ? rec.items : Array.isArray(data) ? data : [];
        const items = rawItems
          .map(normalizeItem)
          .filter((i): i is ScreenerItem => i !== null);
        if (items.length > 0) {
          return {
            result: {
              items,
              total: typeof rec.total === "number" ? rec.total : items.length,
            },
            source: "live",
          };
        }
      }
    } catch {
      /* fall through to mock */
    }
  }
  return { result: applyFilters(filters), source: "mock" };
}
