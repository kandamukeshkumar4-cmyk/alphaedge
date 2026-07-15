import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

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

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

function resolveFetcher(input?: Fetcher): Fetcher {
  return input ?? fetch;
}

async function resolveBase(): Promise<string> {
  return (await ensureApiBase()) || API_BASE;
}

function authHeaders(token?: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiError(response: Response): Promise<Error> {
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
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<TraderProfile | null> {
  const base = input?.apiBase ?? (await resolveBase());
  if (!hasLiveApi(base)) return null;
  try {
    const response = await resolveFetcher(input?.fetcher)(
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
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<FollowingEntry[]> {
  const base = input?.apiBase ?? (await resolveBase());
  if (!hasLiveApi(base) || !token) return [];
  try {
    const response = await resolveFetcher(input?.fetcher)(
      apiUrl("/api/v1/social/following", base),
      { cache: "no-store", headers: authHeaders(token) },
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
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<FollowResponse> {
  return mutateFollow("POST", name, token, input);
}

export async function unfollowTrader(
  name: string,
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<FollowResponse> {
  return mutateFollow("DELETE", name, token, input);
}

async function mutateFollow(
  method: "POST" | "DELETE",
  name: string,
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<FollowResponse> {
  const base = input?.apiBase ?? (await resolveBase());
  if (!hasLiveApi(base) || !token) {
    throw new Error("Log in to follow traders.");
  }
  const response = await resolveFetcher(input?.fetcher)(
    apiUrl(`/api/v1/social/follow/${encodeURIComponent(name)}`, base),
    { method, cache: "no-store", headers: authHeaders(token) },
  );
  if (!response.ok) throw await apiError(response);
  return (await response.json()) as FollowResponse;
}

export async function fetchSocialFeed(
  token: string,
  input?: {
    apiBase?: string;
    cursor?: string | null;
    limit?: number;
    fetcher?: Fetcher;
  },
): Promise<SocialFeedPage> {
  const limit = input?.limit ?? 50;
  const empty: SocialFeedPage = {
    items: [],
    next_cursor: null,
    limit,
    paper_trading_only: true,
  };
  const base = input?.apiBase ?? (await resolveBase());
  if (!hasLiveApi(base) || !token) return empty;

  const params = new URLSearchParams({ limit: String(limit) });
  if (input?.cursor) params.set("cursor", input.cursor);
  try {
    const response = await resolveFetcher(input?.fetcher)(
      `${apiUrl("/api/v1/social/feed", base)}?${params.toString()}`,
      { cache: "no-store", headers: authHeaders(token) },
    );
    if (!response.ok) return empty;
    return (await response.json()) as SocialFeedPage;
  } catch {
    return empty;
  }
}
