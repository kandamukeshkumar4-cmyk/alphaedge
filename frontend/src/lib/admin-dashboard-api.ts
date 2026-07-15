import { API_BASE } from "./alphaedge-api";
import { adminHeaders } from "./admin-auth";

export type WC2026Status = {
  total_fixtures: number;
  seeded: number;
  resolved: number;
  pending: number;
};

export type WC2026SeedResult = {
  created: number;
  skipped: number;
  fixtures: number;
};

export type WC2026ResolveResult = {
  resolved: number;
  skipped: number;
};

export type AdminMarketRow = {
  slug: string;
  title: string;
  status: string;
  category: string;
  tournament_tag: string | null;
};

export type AdminStats = {
  users: number;
  markets_by_status: { open: number; locked: number; resolved: number; cancelled: number };
  trades: { last_24h: number; last_7d: number };
  forecasts: { locked: number; graded: number };
  table_counts: Record<string, number>;
  generated_at: string;
  cached: boolean;
  cache_ttl_sec: number;
  paper_trading_only: boolean;
};

export type AdminUserRow = {
  id: string;
  email: string;
  display_name: string | null;
  paper_balance: number;
  is_suspended: boolean;
  onboarded: boolean;
  created_at: string | null;
  trade_count: number;
};

export type AdminUsersResponse = {
  users: AdminUserRow[];
  total: number;
  limit: number;
  offset: number;
  paper_trading_only: boolean;
};

export type AdminJobRun = {
  job_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown>;
};

type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; message: string };

async function adminFetch<T>(
  apiKey: string,
  path: string,
  method: "GET" | "POST" = "GET",
): Promise<ApiResult<T>> {
  if (!API_BASE) {
    return { ok: false, message: "Set NEXT_PUBLIC_API_URL to use admin APIs." };
  }
  if (!apiKey.trim()) {
    return { ok: false, message: "Admin API key is required." };
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      cache: "no-store",
      headers: adminHeaders(apiKey),
    });
    if (!response.ok) {
      let message = response.statusText || `HTTP ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // ignore parse errors
      }
      return { ok: false, message };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, message: "Admin API unavailable." };
  }
}

export function fetchWC2026Status(apiKey: string) {
  return adminFetch<WC2026Status>(apiKey, "/api/v1/admin/wc2026/status");
}

export function seedWC2026Markets(apiKey: string) {
  return adminFetch<WC2026SeedResult>(apiKey, "/api/v1/admin/wc2026/seed", "POST");
}

export function resolveWC2026Markets(apiKey: string) {
  return adminFetch<WC2026ResolveResult>(apiKey, "/api/v1/admin/wc2026/resolve", "POST");
}

export function fetchAdminMarkets(
  apiKey: string,
  params?: { limit?: number; tournamentTag?: string },
) {
  const search = new URLSearchParams();
  search.set("limit", String(params?.limit ?? 200));
  if (params?.tournamentTag) {
    search.set("tournament_tag", params.tournamentTag);
  }
  return adminFetch<AdminMarketRow[]>(apiKey, `/api/v1/admin/markets?${search}`);
}

export function fetchAdminJobs(apiKey: string, limit = 5) {
  return adminFetch<{ runs: AdminJobRun[] }>(
    apiKey,
    `/api/v1/admin/jobs?limit=${limit}`,
  );
}

export function fetchAdminStats(apiKey: string) {
  return adminFetch<AdminStats>(apiKey, "/api/v1/admin/stats");
}

/** Per-connector health from admin-gated GET /api/v1/system/sources. */
export type SourceHealthRow = {
  source: string;
  state: string;
  consecutive_failures: number;
  total_successes: number;
  total_failures: number;
  last_error: string | null;
  last_success_age_sec: number | null;
  circuit_open_remaining_sec: number | null;
};

export type SourcesHealthResponse = {
  sources: SourceHealthRow[];
  count: number;
  paper_trading_only: boolean;
};

export function fetchSystemSources(apiKey: string) {
  return adminFetch<SourcesHealthResponse>(apiKey, "/api/v1/system/sources");
}

type AdminActionResponse = { slug: string; status: string; paper_trading_only: boolean };

export function pauseAdminMarket(apiKey: string, slug: string) {
  return adminFetch<AdminActionResponse>(apiKey, `/api/v1/admin/markets/${encodeURIComponent(slug)}/pause`, "POST");
}

export function unpauseAdminMarket(apiKey: string, slug: string) {
  return adminFetch<AdminActionResponse>(apiKey, `/api/v1/admin/markets/${encodeURIComponent(slug)}/unpause`, "POST");
}

export function cancelAdminMarket(apiKey: string, slug: string) {
  return adminFetch<AdminActionResponse>(apiKey, `/api/v1/admin/markets/${encodeURIComponent(slug)}/cancel`, "POST");
}

export function fetchAdminUsers(apiKey: string, params?: { q?: string; limit?: number; offset?: number }) {
  const search = new URLSearchParams({
    limit: String(params?.limit ?? 50),
    offset: String(params?.offset ?? 0),
  });
  if (params?.q?.trim()) search.set("q", params.q.trim());
  return adminFetch<AdminUsersResponse>(apiKey, `/api/v1/admin/users?${search}`);
}

type AdminUserActionResponse = { id: string; email: string; is_suspended: boolean; paper_trading_only: boolean };

export function suspendAdminUser(apiKey: string, userId: string) {
  return adminFetch<AdminUserActionResponse>(apiKey, `/api/v1/admin/users/${encodeURIComponent(userId)}/suspend`, "POST");
}

export function unsuspendAdminUser(apiKey: string, userId: string) {
  return adminFetch<AdminUserActionResponse>(apiKey, `/api/v1/admin/users/${encodeURIComponent(userId)}/unsuspend`, "POST");
}
