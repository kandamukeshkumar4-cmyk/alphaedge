import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * Public forecast track record — GET /api/v1/track-record (backend G05).
 * Read-only, computed from REAL resolutions only. Field names are a CONTRACT
 * (see goals/loop-grok-backend/API-NOTES.md → G05). Misses count as much as
 * wins: transparency IS the product.
 */
export type CalibrationBin = {
  lower: number;
  upper: number;
  count: number;
  mean_predicted: number | null;
  observed_frequency: number | null;
};

export type BrierPoint = {
  seq: number;
  scored_at: string;
  brier: number;
  cumulative_brier: number;
};

export type ClvHistogramBucket = {
  lower: number | null;
  upper: number | null;
  count: number;
};

export type ClvSummary = {
  count: number;
  mean: number;
  min: number;
  max: number;
  positive_share: number;
  histogram: ClvHistogramBucket[];
};

export type TrackRecordSource = "forecast_scores" | "paper_orders" | "none";

export type PublicTrackRecord = {
  n: number;
  thin_data: boolean;
  thin_data_threshold: number;
  brier_score: number | null;
  calibration_bins: CalibrationBin[];
  brier_over_time: BrierPoint[];
  clv: ClvSummary;
  source: TrackRecordSource;
  last_updated: string | null;
  paper_trading_only: boolean;
  disclaimer: string;
};

/** Plottable reliability point (predicted vs observed) from a filled bin. */
export type ReliabilityPoint = {
  predicted: number;
  observed: number;
  count: number;
};

export type ClvBucketView = {
  label: string;
  count: number;
};

export type TrackRecordView = {
  /** False when source === "none" (no resolved data) — render honest empty. */
  available: boolean;
  source: TrackRecordSource;
  n: number;
  thinData: boolean;
  threshold: number;
  /** Prominent provisional caveat when thin_data is true. */
  caveat: string | null;
  brierLabel: string;
  reliabilityPoints: ReliabilityPoint[];
  hasReliability: boolean;
  brierSeries: BrierPoint[];
  hasBrierSeries: boolean;
  clvBuckets: ClvBucketView[];
  hasClv: boolean;
  clvMeanLabel: string;
  clvPositiveShareLabel: string;
  lastUpdatedLabel: string | null;
  disclaimer: string;
};

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

/** Human label for one CLV histogram bucket (open-ended tails use ≤ / ≥). */
export function formatClvBucketLabel(bucket: ClvHistogramBucket): string {
  const { lower, upper } = bucket;
  if (lower === null && upper !== null) return `≤ ${(upper * 100).toFixed(0)}%`;
  if (upper === null && lower !== null) return `≥ ${(lower * 100).toFixed(0)}%`;
  if (lower === null && upper === null) return "all";
  return `${((lower ?? 0) * 100).toFixed(0)}…${((upper ?? 0) * 100).toFixed(0)}%`;
}

/** Pure transform: raw G05 response → view model. Honest empty when no data. */
export function buildTrackRecordView(raw: PublicTrackRecord | null): TrackRecordView {
  const empty: TrackRecordView = {
    available: false,
    source: "none",
    n: 0,
    thinData: false,
    threshold: 30,
    caveat: null,
    brierLabel: "—",
    reliabilityPoints: [],
    hasReliability: false,
    brierSeries: [],
    hasBrierSeries: false,
    clvBuckets: [],
    hasClv: false,
    clvMeanLabel: "—",
    clvPositiveShareLabel: "—",
    lastUpdatedLabel: null,
    disclaimer:
      "Research metrics from real resolutions only. Paper trading only — simulated funds, no execution.",
  };

  if (!raw || raw.source === "none" || raw.n <= 0) {
    return { ...empty, disclaimer: raw?.disclaimer ?? empty.disclaimer };
  }

  const reliabilityPoints: ReliabilityPoint[] = (raw.calibration_bins ?? [])
    .filter(
      (b) => b.count > 0 && b.mean_predicted !== null && b.observed_frequency !== null,
    )
    .map((b) => ({
      predicted: b.mean_predicted as number,
      observed: b.observed_frequency as number,
      count: b.count,
    }))
    .sort((a, b) => a.predicted - b.predicted);

  const clvBuckets: ClvBucketView[] = (raw.clv?.histogram ?? []).map((bucket) => ({
    label: formatClvBucketLabel(bucket),
    count: bucket.count,
  }));

  return {
    available: true,
    source: raw.source,
    n: raw.n,
    thinData: raw.thin_data,
    threshold: raw.thin_data_threshold,
    caveat: raw.thin_data
      ? `Provisional (n=${raw.n}) — fewer than ${raw.thin_data_threshold} resolved outcomes. Treat these numbers as indicative, not proven.`
      : null,
    brierLabel: raw.brier_score === null ? "—" : raw.brier_score.toFixed(3),
    reliabilityPoints,
    hasReliability: reliabilityPoints.length > 0,
    brierSeries: raw.brier_over_time ?? [],
    hasBrierSeries: (raw.brier_over_time ?? []).length > 0,
    clvBuckets,
    hasClv: (raw.clv?.count ?? 0) > 0,
    clvMeanLabel: raw.clv ? signedPct(raw.clv.mean) : "—",
    clvPositiveShareLabel: raw.clv ? pct(raw.clv.positive_share) : "—",
    lastUpdatedLabel: raw.last_updated
      ? new Date(raw.last_updated).toLocaleDateString()
      : null,
    disclaimer: raw.disclaimer ?? empty.disclaimer,
  };
}

function signedPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

/** Fetch the public track record. Returns null with no live API or on error. */
export async function fetchPublicTrackRecord(
  signal?: AbortSignal,
): Promise<PublicTrackRecord | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/track-record", base), {
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicTrackRecord;
  } catch {
    return null;
  }
}
