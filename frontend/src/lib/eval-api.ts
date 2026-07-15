import { API_BASE } from "./alphaedge-api";
import { adminHeaders } from "./admin-auth";

export type DriftPoint = {
  id: string;
  computed_at: string | null;
  window_n: number;
  rolling_brier: number | null;
  rolling_ece: number | null;
  baseline_brier: number | null;
  baseline_ece: number | null;
  brier_delta: number | null;
  ece_delta: number | null;
  degraded: boolean;
};

export type DriftSeriesResponse = {
  series: DriftPoint[];
  count: number;
  latest_degraded: boolean;
  paper_trading_only: boolean;
};

export type ModelRegistryEntry = {
  id: string;
  name: string;
  version: string | number;
  artifact_path: string | null;
  training_data_hash: string | null;
  metrics: {
    brier: number | null;
    calibration: number | null;
    expected_calibration_error: number | null;
    [key: string]: unknown;
  };
  is_active: boolean;
  created_at: string | null;
};

export type ModelRegistryResponse = {
  models: ModelRegistryEntry[];
  active_model_id: string | null;
  count: number;
};

function endpoint(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

export async function fetchDriftSeries(): Promise<DriftSeriesResponse | null> {
  try {
    const response = await fetch(endpoint("/api/v1/eval/drift"), { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as DriftSeriesResponse;
  } catch {
    return null;
  }
}

export async function fetchModelRegistry(
  apiKey: string,
): Promise<ModelRegistryResponse | null> {
  if (!apiKey.trim()) return null;
  try {
    const response = await fetch(endpoint("/api/v1/models"), {
      cache: "no-store",
      headers: adminHeaders(apiKey),
    });
    if (!response.ok) return null;
    return (await response.json()) as ModelRegistryResponse;
  } catch {
    return null;
  }
}
