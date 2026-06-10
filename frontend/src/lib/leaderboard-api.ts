import { API_BASE } from "./alphaedge-api";

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
  if (!API_BASE) {
    return [];
  }

  const response = await fetch(`${API_BASE}/api/v1/leaderboard`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Leaderboard HTTP ${response.status}`);
  }

  const body = (await response.json()) as LeaderboardResponse;
  return body.entries;
}
