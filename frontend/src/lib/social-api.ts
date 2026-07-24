/**
 * Loop 104 — community API client.
 *
 * The live API is attempted first. When the API is unavailable, typed in-memory
 * paper fixtures keep the read surfaces useful without pretending that a live
 * community action succeeded. UI components never call fetch directly.
 *
 * PAPER_TRADING_ONLY — stories are historical discussion records. This module
 * has no order, risk, sizing, or execution client.
 */

import { API_BASE, apiUrl, ensureApiBase, formatApiDetail, hasLiveApi } from "@/lib/alphaedge-api";

export type Actor = {
  handle: string;
  display_name: string;
  avatar_url: string | null;
};

export type StoryKind = "trade" | "forecast" | "watchlist" | "note";

export type Story = {
  id: string;
  kind: StoryKind;
  actor: Actor;
  market_slug: string | null;
  market_title: string | null;
  headline: string;
  body: string | null;
  created_at: string;
  reactions: { like: number };
  reacted: boolean;
  comment_count: number;
};

export type Comment = {
  id: string;
  actor: Actor;
  body: string;
  created_at: string;
};

export type StoryPage = {
  items: Story[];
  next_cursor: string | null;
};

export type CommentPage = {
  items: Comment[];
};

export type SharedWatchlistItem = {
  market_slug: string;
  market_title: string;
  added_at: string;
};

export type SharedWatchlist = {
  handle: string;
  display_name: string;
  items: SharedWatchlistItem[];
};

export type ReactionResponse = {
  reactions: { like: number };
  reacted: boolean;
};

export type WatchlistShareResponse = {
  public: boolean;
  share_url: string;
};

export type ApiSource = "live" | "mock";

export type SocialResult<T> = {
  data: T;
  source: ApiSource;
};

export class SocialApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "SocialApiError";
    this.status = status;
  }
}

export function isSocialApiError(error: unknown): error is SocialApiError {
  return error instanceof SocialApiError;
}

// ---------------------------------------------------------------------------
// Normalizers — keep the UI on the frozen contract even when an upstream
// response is malformed or has optional fields from an older deployment.
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function asStringOrNull(value: unknown): string | null {
  return value === null || value === undefined ? null : asString(value);
}

function asNonNegativeInt(value: unknown, fallback = 0): number {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) && numeric >= 0 ? Math.trunc(numeric) : fallback;
}

function normalizeActor(raw: unknown): Actor | null {
  const record = asRecord(raw);
  const handle = asString(record.handle);
  const displayName = asString(record.display_name);
  if (!handle || !displayName) return null;
  return {
    handle,
    display_name: displayName,
    avatar_url: asStringOrNull(record.avatar_url),
  };
}

function normalizeStory(raw: unknown): Story | null {
  const record = asRecord(raw);
  const actor = normalizeActor(record.actor);
  const id = asString(record.id);
  const headline = asString(record.headline);
  const createdAt = asString(record.created_at);
  const kind = record.kind;
  if (
    !actor ||
    !id ||
    !headline ||
    !createdAt ||
    (kind !== "trade" &&
      kind !== "forecast" &&
      kind !== "watchlist" &&
      kind !== "note")
  ) {
    return null;
  }

  const reactions = asRecord(record.reactions);
  return {
    id,
    kind,
    actor,
    market_slug: asStringOrNull(record.market_slug),
    market_title: asStringOrNull(record.market_title),
    headline,
    body: asStringOrNull(record.body),
    created_at: createdAt,
    reactions: { like: asNonNegativeInt(reactions.like) },
    reacted: record.reacted === true,
    comment_count: asNonNegativeInt(record.comment_count),
  };
}

function normalizeComment(raw: unknown): Comment | null {
  const record = asRecord(raw);
  const actor = normalizeActor(record.actor);
  const id = asString(record.id);
  const body = asString(record.body);
  const createdAt = asString(record.created_at);
  if (!actor || !id || !body || !createdAt) return null;
  return { id, actor, body, created_at: createdAt };
}

function normalizeStoryPage(raw: unknown): StoryPage | null {
  const record = asRecord(raw);
  if (!Array.isArray(record.items)) return null;
  const nextCursor = record.next_cursor;
  if (nextCursor !== null && nextCursor !== undefined && typeof nextCursor !== "string") {
    return null;
  }
  return {
    items: record.items
      .map(normalizeStory)
      .filter((story): story is Story => story !== null),
    next_cursor: nextCursor ?? null,
  };
}

function normalizeCommentPage(raw: unknown): CommentPage | null {
  const record = asRecord(raw);
  if (!Array.isArray(record.items)) return null;
  return {
    items: record.items
      .map(normalizeComment)
      .filter((comment): comment is Comment => comment !== null),
  };
}

function normalizeReactionResponse(raw: unknown): ReactionResponse | null {
  const record = asRecord(raw);
  const reactions = asRecord(record.reactions);
  if (typeof record.reacted !== "boolean") return null;
  return {
    reactions: { like: asNonNegativeInt(reactions.like) },
    reacted: record.reacted,
  };
}

function normalizeSharedWatchlist(raw: unknown): SharedWatchlist | null {
  const record = asRecord(raw);
  const handle = asString(record.handle);
  const displayName = asString(record.display_name);
  if (!handle || !displayName || !Array.isArray(record.items)) return null;
  const items = record.items
    .map((item) => {
      const row = asRecord(item);
      const marketSlug = asString(row.market_slug);
      const marketTitle = asString(row.market_title);
      const addedAt = asString(row.added_at);
      return marketSlug && marketTitle && addedAt
        ? { market_slug: marketSlug, market_title: marketTitle, added_at: addedAt }
        : null;
    })
    .filter((item): item is SharedWatchlistItem => item !== null);
  return { handle, display_name: displayName, items };
}

// ---------------------------------------------------------------------------
// Typed paper fallback
// ---------------------------------------------------------------------------

const MOCK_ACTOR: Actor = {
  handle: "paper-analyst",
  display_name: "Paper Analyst",
  avatar_url: null,
};

const MOCK_STORIES: Story[] = [
  {
    id: "mock-community-1",
    kind: "forecast",
    actor: MOCK_ACTOR,
    market_slug: "nba-2025-01-15-lal-bos",
    market_title: "Lakers vs Celtics",
    headline: "The closing line is still the benchmark for this paper forecast",
    body: "A research note on calibration, not a trading instruction.",
    created_at: "2026-07-24T12:00:00.000Z",
    reactions: { like: 3 },
    reacted: false,
    comment_count: 1,
  },
  {
    id: "mock-community-2",
    kind: "watchlist",
    actor: MOCK_ACTOR,
    market_slug: null,
    market_title: null,
    headline: "Shared watchlists keep market context visible to the desk",
    body: "A watchlist is a research collection; it never submits an order.",
    created_at: "2026-07-24T09:30:00.000Z",
    reactions: { like: 1 },
    reacted: false,
    comment_count: 0,
  },
];

const MOCK_COMMENTS: Record<string, Comment[]> = {
  "mock-community-1": [
    {
      id: "mock-comment-1",
      actor: { handle: "line-watcher", display_name: "Line Watcher", avatar_url: null },
      body: "Useful distinction between research context and an executable action.",
      created_at: "2026-07-24T12:20:00.000Z",
    },
  ],
};

let mockLikeCounts = new Map(MOCK_STORIES.map((story) => [story.id, story.reactions.like]));

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the social API)
// ---------------------------------------------------------------------------

type SocialFetch = typeof fetch;
type LiveResult<T> = {
  data: T | null;
  error: SocialApiError | null;
};

let socialFetch: SocialFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setSocialFetch(fn: SocialFetch): void {
  socialFetch = fn;
}

/** Restore the default fetch layer (test hygiene). */
export function resetSocialFetch(): void {
  socialFetch = (...args) => fetch(...args);
}

async function tryLiveJson<T>(
  path: string,
  token: string | null,
  init?: Pick<RequestInit, "method" | "body">,
): Promise<LiveResult<T>> {
  const base = (await ensureApiBase()) || undefined;
  if (!base || !hasLiveApi(base)) return { data: null, error: null };
  try {
    const res = await socialFetch(apiUrl(path, base), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store",
    });
    if (!res.ok) {
      let detail: unknown = null;
      try {
        const body = (await res.json()) as { detail?: unknown };
        detail = body.detail;
      } catch {
        // Keep the status text when the backend returns no JSON body.
      }
      return {
        data: null,
        error: new SocialApiError(
          formatApiDetail(detail, res.statusText || `Request failed (${res.status})`),
          res.status,
        ),
      };
    }
    return { data: (await res.json()) as T, error: null };
  } catch {
    // Network failure is the typed-fallback case; HTTP errors remain visible
    // to callers so validation failures are not hidden.
    return { data: null, error: null };
  }
}

function requireToken(token: string | null): string {
  if (!token) throw new SocialApiError("Sign in to use this community action.", 401);
  return token;
}

/** Public story feed. Live first; paper fixture fallback when unavailable. */
export async function listStories(
  limit = 20,
  cursor: string | null = null,
  token: string | null = null,
): Promise<SocialResult<StoryPage>> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  const live = await tryLiveJson<unknown>(
    `/api/v1/social/stories?${params.toString()}`,
    token,
  );
  const normalized = normalizeStoryPage(live.data);
  if (normalized) return { data: normalized, source: "live" };
  return {
    data: { items: cursor ? [] : MOCK_STORIES, next_cursor: null },
    source: "mock",
  };
}

/** Public comments for a story. */
export async function listComments(
  storyId: string,
  limit = 50,
): Promise<SocialResult<CommentPage>> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/social/stories/${encodeURIComponent(storyId)}/comments?limit=${limit}`,
    null,
  );
  const normalized = normalizeCommentPage(live.data);
  if (normalized) return { data: normalized, source: "live" };
  return { data: { items: MOCK_COMMENTS[storyId] ?? [] }, source: "mock" };
}

/** Add one comment. HTTP 422 is preserved for the inline composer error. */
export async function addComment(
  token: string | null,
  storyId: string,
  body: string,
): Promise<SocialResult<Comment>> {
  const authToken = requireToken(token);
  const trimmed = body.trim();
  if (!trimmed || trimmed.length > 500) {
    throw new SocialApiError("Comment must be between 1 and 500 characters.", 422);
  }
  const live = await tryLiveJson<unknown>(
    `/api/v1/social/stories/${encodeURIComponent(storyId)}/comments`,
    authToken,
    { method: "POST", body: JSON.stringify({ body: trimmed }) },
  );
  const normalized = normalizeComment(live.data);
  if (normalized) return { data: normalized, source: "live" };
  if (live.error) throw live.error;
  const fallback: Comment = {
    id: `mock-comment-${Date.now()}`,
    actor: { handle: "you", display_name: "You", avatar_url: null },
    body: trimmed,
    created_at: new Date().toISOString(),
  };
  return { data: fallback, source: "mock" };
}

/** Optimistically add a paper like when the live endpoint is unavailable. */
export async function react(
  token: string | null,
  storyId: string,
): Promise<SocialResult<ReactionResponse>> {
  const authToken = requireToken(token);
  const live = await tryLiveJson<unknown>(
    `/api/v1/social/stories/${encodeURIComponent(storyId)}/reactions`,
    authToken,
    { method: "POST", body: JSON.stringify({ kind: "like" }) },
  );
  const normalized = normalizeReactionResponse(live.data);
  if (normalized) return { data: normalized, source: "live" };
  if (live.error) throw live.error;
  const count = (mockLikeCounts.get(storyId) ?? 0) + 1;
  mockLikeCounts.set(storyId, count);
  return { data: { reactions: { like: count }, reacted: true }, source: "mock" };
}

/** Remove a paper like when the live endpoint is unavailable. */
export async function unreact(
  token: string | null,
  storyId: string,
): Promise<SocialResult<ReactionResponse>> {
  const authToken = requireToken(token);
  const live = await tryLiveJson<unknown>(
    `/api/v1/social/stories/${encodeURIComponent(storyId)}/reactions/like`,
    authToken,
    { method: "DELETE" },
  );
  const normalized = normalizeReactionResponse(live.data);
  if (normalized) return { data: normalized, source: "live" };
  if (live.error) throw live.error;
  const count = Math.max(0, (mockLikeCounts.get(storyId) ?? 0) - 1);
  mockLikeCounts.set(storyId, count);
  return { data: { reactions: { like: count }, reacted: false }, source: "mock" };
}

/** Public shared watchlist. Empty fallback is honest when no live profile exists. */
export async function getSharedWatchlist(
  handle: string,
): Promise<SocialResult<SharedWatchlist>> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/watchlist/shared/${encodeURIComponent(handle)}`,
    null,
  );
  const normalized = normalizeSharedWatchlist(live.data);
  if (normalized) return { data: normalized, source: "live" };
  return {
    data: { handle, display_name: handle, items: [] },
    source: "mock",
  };
}

/** Toggle whether the authenticated paper watchlist is publicly shareable. */
export async function setWatchlistShare(
  token: string | null,
  isPublic: boolean,
): Promise<SocialResult<WatchlistShareResponse>> {
  const authToken = requireToken(token);
  const live = await tryLiveJson<unknown>(
    "/api/v1/watchlist/share",
    authToken,
    { method: "POST", body: JSON.stringify({ public: isPublic }) },
  );
  const record = asRecord(live.data);
  const shareUrl = asString(record.share_url);
  if (typeof record.public === "boolean" && shareUrl) {
    return {
      data: { public: record.public, share_url: shareUrl },
      source: "live",
    };
  }
  if (live.error) throw live.error;
  return {
    data: { public: isPublic, share_url: "/w/me" },
    source: "mock",
  };
}

// ---------------------------------------------------------------------------
// Existing trader/social feed client — retained for the neighboring trader
// surface in this shared module. The community story contract above is
// independent from this historical paper-trade activity contract.
// ---------------------------------------------------------------------------

export type TraderProfile = {
  username: string;
  member_since: string;
  trade_count: number;
  settled_trade_count: number;
  win_rate: number;
  roi: number;
  followers_count: number;
  following_count: number;
  paper_trading_only: boolean;
};

export type FollowResponse = {
  username: string;
  following: boolean;
  changed: boolean;
  followers_count: number;
  paper_trading_only: boolean;
};

export type FollowingEntry = {
  username: string;
  member_since: string;
};

export type FollowingResponse = {
  items: FollowingEntry[];
  total: number;
  paper_trading_only: boolean;
};

export type SocialTradeActivity = {
  order_id: string;
  trader: string;
  slug: string;
  side: string;
  outcome: string;
  shares: number;
  price: number;
  action: string;
  created_at: string;
};

export type SocialFeedPage = {
  items: SocialTradeActivity[];
  next_cursor: string | null;
  limit: number;
  paper_trading_only: boolean;
};

type LegacyFetcher = (url: string, init?: RequestInit) => Promise<Response>;

function resolveLegacyFetcher(input?: LegacyFetcher): LegacyFetcher {
  return input ?? fetch;
}

async function resolveLegacyBase(): Promise<string> {
  return (await ensureApiBase()) || API_BASE;
}

function legacyAuthHeaders(token?: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function legacyApiError(response: Response): Promise<Error> {
  let detail = response.statusText || `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // Keep the status text when the API returns a non-JSON error.
  }
  return new Error(detail);
}

export async function fetchTraderProfile(
  name: string,
  input?: { apiBase?: string; fetcher?: LegacyFetcher },
): Promise<TraderProfile | null> {
  const base = input?.apiBase ?? (await resolveLegacyBase());
  if (!hasLiveApi(base)) return null;
  try {
    const response = await resolveLegacyFetcher(input?.fetcher)(
      apiUrl(`/api/v1/social/traders/${encodeURIComponent(name)}`, base),
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    return (await response.json()) as TraderProfile;
  } catch {
    return null;
  }
}

export async function fetchFollowing(
  token: string,
  input?: { apiBase?: string; fetcher?: LegacyFetcher },
): Promise<FollowingEntry[]> {
  const base = input?.apiBase ?? (await resolveLegacyBase());
  if (!hasLiveApi(base) || !token) return [];
  try {
    const response = await resolveLegacyFetcher(input?.fetcher)(
      apiUrl("/api/v1/social/following", base),
      { cache: "no-store", headers: legacyAuthHeaders(token) },
    );
    if (!response.ok) return [];
    const body = (await response.json()) as FollowingResponse;
    return Array.isArray(body.items) ? body.items : [];
  } catch {
    return [];
  }
}

export async function followTrader(
  name: string,
  token: string,
  input?: { apiBase?: string; fetcher?: LegacyFetcher },
): Promise<FollowResponse> {
  return mutateFollow("POST", name, token, input);
}

export async function unfollowTrader(
  name: string,
  token: string,
  input?: { apiBase?: string; fetcher?: LegacyFetcher },
): Promise<FollowResponse> {
  return mutateFollow("DELETE", name, token, input);
}

async function mutateFollow(
  method: "POST" | "DELETE",
  name: string,
  token: string,
  input?: { apiBase?: string; fetcher?: LegacyFetcher },
): Promise<FollowResponse> {
  const base = input?.apiBase ?? (await resolveLegacyBase());
  if (!hasLiveApi(base) || !token) {
    throw new Error("Log in to follow traders.");
  }
  const response = await resolveLegacyFetcher(input?.fetcher)(
    apiUrl(`/api/v1/social/follow/${encodeURIComponent(name)}`, base),
    { method, cache: "no-store", headers: legacyAuthHeaders(token) },
  );
  if (!response.ok) throw await legacyApiError(response);
  return (await response.json()) as FollowResponse;
}

export async function fetchSocialFeed(
  token: string,
  input?: {
    apiBase?: string;
    cursor?: string | null;
    limit?: number;
    fetcher?: LegacyFetcher;
  },
): Promise<SocialFeedPage> {
  const limit = input?.limit ?? 50;
  const empty: SocialFeedPage = {
    items: [],
    next_cursor: null,
    limit,
    paper_trading_only: true,
  };
  const base = input?.apiBase ?? (await resolveLegacyBase());
  if (!hasLiveApi(base) || !token) return empty;

  const params = new URLSearchParams({ limit: String(limit) });
  if (input?.cursor) params.set("cursor", input.cursor);
  try {
    const response = await resolveLegacyFetcher(input?.fetcher)(
      `${apiUrl("/api/v1/social/feed", base)}?${params.toString()}`,
      { cache: "no-store", headers: legacyAuthHeaders(token) },
    );
    if (!response.ok) return empty;
    return (await response.json()) as SocialFeedPage;
  } catch {
    return empty;
  }
}
