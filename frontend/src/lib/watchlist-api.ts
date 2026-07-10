import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

/**
 * W01 — Watchlist client (backend J01, see goals/loop-v5/STATE.md).
 *
 * Per-user (JWT) bookmarks of market slugs. These are the ONLY non-GET calls in
 * the V5 frontend track and they are watchlist bookmarks, NOT orders — there is
 * no order path here. GET/POST/DELETE /api/v1/watchlist with the Bearer session.
 *
 * All view-model logic is pure and tolerant of absent fields (the backend
 * composes existing services, so snapshot/edge may be null on any entry). We
 * degrade gracefully and never fabricate an edge or a last-move.
 */

/** One tracked market as returned by GET /api/v1/watchlist. */
export type WatchlistEntry = {
  slug: string;
  title?: string | null;
  snapshot?: {
    yes_price?: number | null;
    last_move_pts?: number | null;
  } | null;
  edge?: {
    predicted_prob?: number | null;
    edge_vs_book?: number | null;
  } | null;
  created_at?: string | null;
};

export type WatchlistResponse = {
  items?: WatchlistEntry[];
  paper_trading_only?: boolean;
};

/** Row-shaped view model for the /watchlist page. */
export type WatchlistItemView = {
  slug: string;
  title: string;
  yesPriceLabel: string;
  hasYesPrice: boolean;
  edgeLabel: string | null;
  edgeTone: "up" | "down" | "neutral";
  lastMoveLabel: string | null;
  lastMoveTone: "up" | "down" | "neutral";
};

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function tone(value: number | null): "up" | "down" | "neutral" {
  if (value === null || Math.abs(value) < 1e-9) return "neutral";
  return value > 0 ? "up" : "down";
}

/** Pure: one raw entry → view row. Never invents missing numbers. */
export function buildWatchlistItemView(entry: WatchlistEntry): WatchlistItemView {
  const yes = num(entry.snapshot?.yes_price);
  const edge = num(entry.edge?.edge_vs_book);
  const move = num(entry.snapshot?.last_move_pts);
  return {
    slug: entry.slug,
    title: entry.title?.trim() || entry.slug,
    yesPriceLabel: yes === null ? "—" : `${Math.round(yes * 100)}¢`,
    hasYesPrice: yes !== null,
    edgeLabel: edge === null ? null : `${edge >= 0 ? "+" : ""}${(edge * 100).toFixed(1)} pts`,
    edgeTone: tone(edge),
    lastMoveLabel: move === null ? null : `${move >= 0 ? "+" : ""}${move.toFixed(1)} pts`,
    lastMoveTone: tone(move),
  };
}

/** Pure: full response → rows (newest first, honest empty on null/missing). */
export function buildWatchlistView(raw: WatchlistResponse | null): WatchlistItemView[] {
  if (!raw || !Array.isArray(raw.items)) return [];
  return raw.items
    .filter((e) => typeof e?.slug === "string" && e.slug.length > 0)
    .map(buildWatchlistItemView);
}

/**
 * Pure optimistic toggle: given the current tracked slug set and a slug,
 * return the next set and the mutation the caller should send. Adding when
 * absent, removing when present.
 */
export type WatchlistToggle = {
  next: string[];
  action: "add" | "remove";
};

export function toggleWatchlistSlug(current: string[], slug: string): WatchlistToggle {
  const set = new Set(current);
  if (set.has(slug)) {
    set.delete(slug);
    return { next: [...set], action: "remove" };
  }
  set.add(slug);
  return { next: [...set], action: "add" };
}

// ── Network (side-effectful; not exercised by the pure vitest) ──────────────

async function baseAndLive(): Promise<string | null> {
  const base = (await ensureApiBase()) || API_BASE;
  return hasLiveApi(base) ? base : null;
}

/** GET the caller's tracked markets. Returns [] with no live API / no token. */
export async function fetchWatchlist(token: string | null): Promise<WatchlistEntry[]> {
  if (!token) return [];
  const base = await baseAndLive();
  if (base === null) return [];
  try {
    const res = await fetch(apiUrl("/api/v1/watchlist", base), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as WatchlistResponse;
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

/** POST a bookmark. Returns true on success. */
export async function addWatchlist(token: string, slug: string): Promise<boolean> {
  const base = await baseAndLive();
  if (base === null) return false;
  try {
    const res = await fetch(apiUrl("/api/v1/watchlist", base), {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ slug }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** DELETE a bookmark. Returns true on success. */
export async function removeWatchlist(token: string, slug: string): Promise<boolean> {
  const base = await baseAndLive();
  if (base === null) return false;
  try {
    const res = await fetch(apiUrl(`/api/v1/watchlist/${encodeURIComponent(slug)}`, base), {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}
