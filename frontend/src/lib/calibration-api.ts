import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * Real calibration bins from GET /api/v1/eval/calibration (eval_routes.py).
 * Each bin buckets resolved evaluations by predicted probability and reports
 * the mean predicted prob (x), the observed outcome frequency (y), and the
 * sample count. Empty bins carry count=0 and are dropped by the curve builder.
 *
 * P07: replaces the previous synthetic x-spread. The upcoming G05
 * `/api/v1/track-record` will add an explicit `thin_data` flag; until it ships
 * (and is documented in loop-grok-backend/API-NOTES.md) we derive the
 * provisional label from the total resolved sample count.
 */
export type CalibrationBin = {
  bin: number;
  count: number;
  mean_pred: number;
  mean_outcome: number;
};

export type CalibrationPoint = {
  predicted: number;
  observed: number;
  n: number;
};

export type CalibrationCurve = {
  points: CalibrationPoint[];
  totalN: number;
  provisional: boolean;
};

// UI heuristic for "thin data" until the backend exposes a real thin_data flag.
export const PROVISIONAL_MIN_SAMPLES = 50;

/** Pure transform: real bins → plottable curve + provisional/thin-data flag. */
export function buildCalibrationCurve(
  bins: CalibrationBin[],
  provisionalMin: number = PROVISIONAL_MIN_SAMPLES,
): CalibrationCurve {
  const filled = bins.filter((b) => b.count > 0);
  const points = filled
    .map((b) => ({ predicted: b.mean_pred, observed: b.mean_outcome, n: b.count }))
    .sort((a, b) => a.predicted - b.predicted);
  const totalN = filled.reduce((sum, b) => sum + b.count, 0);
  return { points, totalN, provisional: totalN < provisionalMin };
}

/** Fetch real calibration bins. Returns [] when no live API or on error. */
export async function fetchCalibrationBins(signal?: AbortSignal): Promise<CalibrationBin[]> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return [];
  try {
    const res = await fetch(apiUrl("/api/v1/eval/calibration", base), {
      cache: "no-store",
      signal,
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { bins?: CalibrationBin[] };
    return Array.isArray(data.bins) ? data.bins : [];
  } catch {
    return [];
  }
}
