import type { LockForecastMessage } from "./messaging";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type ForecastLifecycleSummary = {
  unresolved_count: number;
  recently_resolved_count: number;
  unresolved: Array<unknown>;
  recently_resolved: Array<unknown>;
};

export async function sendForecastToBackend(input: {
  apiBase: string;
  message: LockForecastMessage;
  idempotencyKey: string;
  fetcher?: Fetcher;
}): Promise<{ ok: true; data?: unknown } | { ok: false; error: string; status?: number }> {
  const fetcher = input.fetcher ?? fetch;
  const response = await fetcher(`${input.apiBase}${input.message.endpoint}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "Idempotency-Key": input.idempotencyKey,
    },
    body: JSON.stringify(input.message.payload),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    return {
      ok: false,
      error: detailFrom(data) ?? `HTTP ${response.status}`,
      status: response.status,
    };
  }
  return { ok: true, data };
}

export async function fetchForecastLifecycle(input: {
  apiBase: string;
  token: string;
  fetcher?: Fetcher;
}): Promise<ForecastLifecycleSummary> {
  const fetcher = input.fetcher ?? fetch;
  const response = await fetcher(`${input.apiBase}/api/v1/forecasters/me/forecast-lifecycle`, {
    headers: {
      "X-Forecaster-Token": input.token,
    },
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as ForecastLifecycleSummary;
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function detailFrom(data: unknown): string | null {
  if (data && typeof data === "object" && "detail" in data) {
    return String((data as { detail: unknown }).detail);
  }
  return null;
}
