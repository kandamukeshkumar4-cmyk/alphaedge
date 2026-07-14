// Public activity API client: alerts + raw signal events (engine room).
// Degrades to empty lists when the backend is down, like polyscout-api.
import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

export type AlertItem = {
  id: string;
  alert_type: string;
  message: string;
  payload: Record<string, unknown>;
  acknowledged: boolean;
  created_at: string;
};

export type SignalEventItem = {
  id: string;
  signal_type: string;
  platform: string;
  market_id: string;
  market_title?: string | null;
  headline_eligible: boolean;
  payload: Record<string, unknown>;
  created_at: string;
};

async function getJson<T>(path: string): Promise<T | null> {
  // Empty API_BASE is valid in browser prod (same-origin Vercel → HF rewrite).
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl(path, base), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchAlerts(opts?: {
  limit?: number;
  alertType?: string;
}): Promise<AlertItem[]> {
  const params = new URLSearchParams();
  params.set("limit", String(opts?.limit ?? 50));
  if (opts?.alertType) params.set("alert_type", opts.alertType);
  const data = await getJson<{ items?: AlertItem[] }>(`/api/v1/alerts?${params}`);
  return data?.items ?? [];
}

export async function fetchSignalEvents(opts?: {
  limit?: number;
  market?: string;
  signalType?: string;
  dedupeWindowMinutes?: number;
}): Promise<SignalEventItem[]> {
  const params = new URLSearchParams();
  params.set("limit", String(opts?.limit ?? 50));
  if (opts?.market) params.set("market", opts.market);
  if (opts?.signalType) params.set("signal_type", opts.signalType);
  if (opts?.dedupeWindowMinutes) {
    params.set("dedupe_window_minutes", String(opts.dedupeWindowMinutes));
  }
  const data = await getJson<{ items?: SignalEventItem[] }>(
    `/api/v1/signals/events?${params}`,
  );
  return data?.items ?? [];
}
