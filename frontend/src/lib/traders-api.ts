import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

export type TraderSort = "realized_pnl" | "roi" | "win_rate";

export type TraderLeaderboardEntry = {
  rank: number;
  username: string;
  realized_pnl: number;
  total_trades: number;
  win_rate: number;
  roi: number;
};

export type TraderLeaderboardPage = {
  entries: TraderLeaderboardEntry[];
  limit: number;
  offset: number;
  total: number;
  sort: TraderSort;
  cached: boolean;
};

export type PublicTraderProfile = {
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

export type TraderDetail = {
  leaderboard: TraderLeaderboardEntry | null;
  profile: PublicTraderProfile | null;
  partial: boolean;
};

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

type RequestOptions = {
  apiBase?: string;
  fetcher?: Fetcher;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeEntry(value: unknown): TraderLeaderboardEntry | null {
  if (!isRecord(value)) return null;
  const rank = finiteNumber(value.rank);
  const realizedPnl = finiteNumber(value.realized_pnl);
  const totalTrades = finiteNumber(value.total_trades);
  const winRate = finiteNumber(value.win_rate);
  const roi = finiteNumber(value.roi);
  if (
    rank === null ||
    typeof value.username !== "string" ||
    realizedPnl === null ||
    totalTrades === null ||
    winRate === null ||
    roi === null
  ) {
    return null;
  }
  return {
    rank,
    username: value.username,
    realized_pnl: realizedPnl,
    total_trades: totalTrades,
    win_rate: winRate,
    roi,
  };
}

function normalizeLeaderboard(
  value: unknown,
  requestedSort: TraderSort,
): TraderLeaderboardPage {
  if (!isRecord(value) || !Array.isArray(value.entries)) {
    throw new Error("The trader ranking response was malformed.");
  }
  return {
    entries: value.entries
      .map(normalizeEntry)
      .filter((entry): entry is TraderLeaderboardEntry => entry !== null),
    limit: finiteNumber(value.limit) ?? 100,
    offset: finiteNumber(value.offset) ?? 0,
    total: finiteNumber(value.total) ?? value.entries.length,
    sort:
      value.sort === "roi" || value.sort === "win_rate" || value.sort === "realized_pnl"
        ? value.sort
        : requestedSort,
    cached: value.cached === true,
  };
}

function normalizeProfile(value: unknown): PublicTraderProfile | null {
  if (!isRecord(value) || typeof value.username !== "string") return null;
  const tradeCount = finiteNumber(value.trade_count);
  const settledTradeCount = finiteNumber(value.settled_trade_count);
  const winRate = finiteNumber(value.win_rate);
  const roi = finiteNumber(value.roi);
  const followersCount = finiteNumber(value.followers_count);
  const followingCount = finiteNumber(value.following_count);
  if (
    typeof value.member_since !== "string" ||
    tradeCount === null ||
    settledTradeCount === null ||
    winRate === null ||
    roi === null ||
    followersCount === null ||
    followingCount === null
  ) {
    return null;
  }
  return {
    username: value.username,
    member_since: value.member_since,
    trade_count: tradeCount,
    settled_trade_count: settledTradeCount,
    win_rate: winRate,
    roi,
    followers_count: followersCount,
    following_count: followingCount,
    paper_trading_only: value.paper_trading_only !== false,
  };
}

async function resolveBase(input?: RequestOptions): Promise<string> {
  const base = input?.apiBase ?? (await ensureApiBase()) ?? API_BASE;
  if (!hasLiveApi(base)) {
    throw new Error("The live trader service is not configured.");
  }
  return base;
}

async function requestJson(
  path: string,
  input?: RequestOptions,
): Promise<{ response: Response; body: unknown }> {
  const base = await resolveBase(input);
  let response: Response;
  try {
    response = await (input?.fetcher ?? fetch)(apiUrl(path, base), {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new Error("The live trader service could not be reached.");
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    if (response.ok) throw new Error("The live trader service returned invalid data.");
  }
  return { response, body };
}

export async function fetchTraders(
  sort: TraderSort = "realized_pnl",
  input?: RequestOptions & { limit?: number; offset?: number },
): Promise<TraderLeaderboardPage> {
  const params = new URLSearchParams({
    limit: String(input?.limit ?? 100),
    offset: String(input?.offset ?? 0),
    sort,
  });
  const { response, body } = await requestJson(
    `/api/v1/leaderboard?${params.toString()}`,
    input,
  );
  if (!response.ok) {
    throw new Error(`Trader rankings are unavailable (HTTP ${response.status}).`);
  }
  return normalizeLeaderboard(body, sort);
}

async function fetchPublicProfile(
  name: string,
  input?: RequestOptions,
): Promise<PublicTraderProfile | null> {
  const { response, body } = await requestJson(
    `/api/v1/social/traders/${encodeURIComponent(name)}`,
    input,
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Trader profile is unavailable (HTTP ${response.status}).`);
  }
  const profile = normalizeProfile(body);
  if (!profile) throw new Error("The trader profile response was malformed.");
  return profile;
}

export async function fetchTraderDetail(
  name: string,
  input?: RequestOptions,
): Promise<TraderDetail | null> {
  const [rankingResult, profileResult] = await Promise.allSettled([
    fetchTraders("realized_pnl", { ...input, limit: 100 }),
    fetchPublicProfile(name, input),
  ]);

  const ranking =
    rankingResult.status === "fulfilled" ? rankingResult.value : null;
  const profile =
    profileResult.status === "fulfilled" ? profileResult.value : null;
  const normalizedName = name.toLocaleLowerCase();
  const leaderboard =
    ranking?.entries.find(
      (entry) => entry.username.toLocaleLowerCase() === normalizedName,
    ) ?? null;

  if (!leaderboard && !profile) {
    if (rankingResult.status === "rejected" && profileResult.status === "rejected") {
      throw rankingResult.reason instanceof Error
        ? rankingResult.reason
        : new Error("Trader data is unavailable.");
    }
    return null;
  }

  return {
    leaderboard,
    profile,
    partial:
      rankingResult.status === "rejected" ||
      profileResult.status === "rejected" ||
      leaderboard === null ||
      profile === null,
  };
}
