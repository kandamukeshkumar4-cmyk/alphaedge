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
