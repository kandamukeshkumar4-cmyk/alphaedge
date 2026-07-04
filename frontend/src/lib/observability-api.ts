// U12 Observability API client — admin trace explorer, calibration drift,
// latency SLO tiles.  Read-only endpoints.  Degrades to empty/null when the
// backend is unavailable (honest unavailable state).
import { API_BASE } from "./alphaedge-api";

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
