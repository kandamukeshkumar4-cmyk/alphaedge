// U12 Observability API client — admin trace explorer, calibration drift,
// latency SLO tiles, plus public loop heartbeats.  Read-only endpoints.
// Degrades to empty/null when the backend is unavailable (honest unavailable).
import { API_BASE, apiUrl } from "./alphaedge-api";

export type AgentRunStep = {
  step_name: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  created_at: string;
};

export type AgentRun = {
  run_id: string;
  market_slug: string;
  status: "approved" | "blocked" | string;
  graph_version: string;
  created_at: string;
  steps: AgentRunStep[];
};

export type TraceExplorerResponse = {
  runs: AgentRun[];
  total: number;
};

export type DriftHistoryPoint = {
  window_days: number;
  brier: number;
};

export type DriftResponse = {
  rolling_brier: number | null;
  baseline_brier: number;
  drift: number | null;
  n_claims: number;
  alarm: boolean;
  insufficient_data: boolean;
  threshold: number;
  history: DriftHistoryPoint[];
};

export type SloTile = {
  name: string;
  unit: string;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  slo_ms: number;
  slo_met: boolean | null; // null = insufficient data
};

export type SloTilesResponse = {
  tiles: SloTile[];
};

/** One row from public GET /api/v1/system/loops. */
export type LoopHeartbeat = {
  name: string;
  planned: boolean;
  running: boolean;
  status: string;
  last_heartbeat: string | null;
  interval_sec: number | null;
  detail: string | null;
};

export type LoopsResponse = {
  plan: string[];
  loops: LoopHeartbeat[];
  paper_trading_only: boolean;
};

export type FetchResult<T> =
  | { ok: true; data: T }
  | { ok: false; message: string };

/** Age in whole seconds since last heartbeat ISO, or null when unknown. */
export function heartbeatAgeSec(
  lastHeartbeatIso: string | null,
  nowMs: number = Date.now(),
): number | null {
  if (!lastHeartbeatIso) return null;
  const ms = Date.parse(lastHeartbeatIso);
  if (!Number.isFinite(ms)) return null;
  return Math.max(0, Math.floor((nowMs - ms) / 1000));
}

/** Humanized relative age ("12s ago", "3m ago"). */
export function formatAgeSec(ageSec: number | null): string {
  if (ageSec == null) return "never";
  if (ageSec < 60) return `${ageSec}s ago`;
  const minutes = Math.floor(ageSec / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Warn when heartbeat age exceeds 2× the configured interval. */
export function isHeartbeatStale(
  ageSec: number | null,
  intervalSec: number | null,
): boolean {
  if (ageSec == null || intervalSec == null || intervalSec <= 0) return false;
  return ageSec > intervalSec * 2;
}

async function getJson<T>(path: string): Promise<T | null> {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Public GET /api/v1/system/loops — no admin key. */
export async function fetchLoops(): Promise<FetchResult<LoopsResponse>> {
  try {
    const res = await fetch(apiUrl("/api/v1/system/loops"), { cache: "no-store" });
    if (!res.ok) {
      return {
        ok: false,
        message: res.statusText || `HTTP ${res.status}`,
      };
    }
    return { ok: true, data: (await res.json()) as LoopsResponse };
  } catch {
    return { ok: false, message: "Loop health API unavailable." };
  }
}

export async function fetchTraces(limit = 20): Promise<TraceExplorerResponse> {
  const data = await getJson<TraceExplorerResponse>(
    `/api/v1/admin/observability/traces?limit=${limit}`,
  );
  return data ?? { runs: [], total: 0 };
}

export async function fetchDrift(): Promise<DriftResponse | null> {
  return getJson<DriftResponse>("/api/v1/admin/observability/drift");
}

export async function fetchSloTiles(): Promise<SloTilesResponse> {
  const data = await getJson<SloTilesResponse>("/api/v1/admin/observability/slo");
  return data ?? { tiles: [] };
}
