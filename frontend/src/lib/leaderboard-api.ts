import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

export type LeaderboardEntry = {
  rank: number;
  username: string;
  realized_pnl: number;
  total_trades: number;
  win_rate: number;
};

export type LeaderboardResponse = {
  entries: LeaderboardEntry[];
};

export async function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return [];
  }

  const response = await fetch(apiUrl("/api/v1/leaderboard", base), {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Leaderboard HTTP ${response.status}`);
  }

  const body = (await response.json()) as LeaderboardResponse;
  return body.entries;
}

// ── Clone leaderboard types (U07) ─────────────────────────────────────────────

export type CloneLeaderboardEntry = {
  clone_id: string;
  name: string;
  owner_id: string;
  nodes: string[];
  edge_threshold: number;
  cooldown_minutes: number;
  version: number;
  n_graded: number;
  accuracy: number | null;
  brier: number | null;
  paper_pnl: number;
  provisional: boolean;
};

export type CloneLeaderboardResponse = {
  leaderboard: CloneLeaderboardEntry[];
  count: number;
  sort_by: string;
  disclaimer: string;
  provisional_min: number;
};

export type CloneRunGrade = {
  run_id: string;
  market_slug: string;
  direction: string;
  price_at_run: number;
  price_at_horizon: number | null;
  verdict: string;
  confidence: number;
  created_at: string;
};

export type CloneScorecardResponse = {
  clone_id: string;
  name: string;
  owner_id: string;
  config: {
    nodes: string[];
    markets: string[];
    edge_threshold: number;
    cooldown_minutes: number;
    version: number;
  };
  metrics: {
    n_graded: number;
    accuracy: number | null;
    brier: number | null;
    paper_pnl: number;
    provisional: boolean;
  };
  claim_history: CloneRunGrade[];
  disclaimer: string;
};

export async function fetchCloneLeaderboard(
  sortBy: "brier" | "pnl" = "brier",
): Promise<CloneLeaderboardResponse> {
  const empty: CloneLeaderboardResponse = {
    leaderboard: [],
    count: 0,
    sort_by: sortBy,
    disclaimer: "All results are paper-traded and calibration-scored.",
    provisional_min: 30,
  };
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return empty;
  }

  const response = await fetch(
    apiUrl(`/api/v1/clones/leaderboard?sort_by=${sortBy}`, base),
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Clone leaderboard HTTP ${response.status}`);
  }
  return (await response.json()) as CloneLeaderboardResponse;
}

export async function fetchCloneScorecard(
  cloneId: string,
): Promise<CloneScorecardResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;

  const response = await fetch(
    apiUrl(`/api/v1/clones/${cloneId}/scorecard`, base),
    { cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Clone scorecard HTTP ${response.status}`);
  }
  return (await response.json()) as CloneScorecardResponse;
}
