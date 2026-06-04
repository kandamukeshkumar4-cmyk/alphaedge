import { API_BASE } from "./alphaedge-api";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type ForecastMode = "live" | "practice";
export type ForecastSource = "web" | "extension" | "backfill";

export type ForecasterCreateResponse = {
  id: string;
  token: string;
  recovery_code: string;
  disclaimer: string;
};

export type ForecastResponse = {
  id: string;
  external_market_id: string;
  seq: number;
  platform: "polymarket" | "kalshi" | "manual";
  market_url: string;
  outcome_label: string;
  user_probability: number;
  market_implied_probability: number | null;
  snapshot_source: string;
  snapshot_metadata: Record<string, unknown>;
  is_independent: boolean;
  mode: ForecastMode;
  source: ForecastSource;
  time_to_resolution_seconds: number | null;
  locked_at: string;
  disclaimer: string;
};

export type DashboardMetrics = {
  resolved_count: number;
  unresolved_count: number;
  headline_count?: number;
  independent_count: number;
  anchored_count: number;
  mean_user_brier: number | null;
  mean_market_brier: number | null;
  mean_brier_delta: number | null;
  synthetic_pnl_total: number;
  brier_provisional: boolean;
  calibration_provisional: boolean;
};

export type PracticeMetrics = {
  resolved_count: number;
  mean_user_brier: number | null;
  mean_brier_delta: number | null;
};

export type CalibrationBin = {
  lower: number;
  upper: number;
  count: number;
  mean_predicted: number | null;
  observed_frequency: number | null;
};

export type CategoryEdge = {
  category: string;
  count: number;
  mean_brier_delta: number | null;
  provisional?: boolean;
};

export type PlatformEdge = {
  platform: "polymarket" | "kalshi" | "manual";
  count: number;
  mean_brier_delta: number | null;
};

export type TimeBucketEdge = {
  bucket: "7d+" | "1-7d" | "6-24h" | "1-6h" | "<1h" | "unknown";
  count: number;
  mean_brier_delta: number | null;
};

export type BrierTrendPoint = {
  seq: number;
  locked_at: string;
  user_brier: number;
  market_brier: number | null;
};

export type ForecastDashboard = {
  forecaster_id: string;
  paper_trading_only: boolean;
  disclaimer: string;
  live: DashboardMetrics;
  practice: PracticeMetrics;
  calibration: CalibrationBin[];
  category_breakdown: CategoryEdge[];
  platform_breakdown?: PlatformEdge[];
  time_breakdown?: TimeBucketEdge[];
  brier_trend?: BrierTrendPoint[];
};

export type BackfillMarket = {
  id: string;
  platform: "polymarket" | "kalshi" | "manual";
  external_id: string;
  url: string;
  title: string;
  category: string;
};

export type CreateAnonymousForecasterInput = {
  apiBase?: string;
  fetcher?: Fetcher;
};

export type RecoverForecasterInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  recoveryCode: string;
};

export type LockForecastInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  token: string;
  url: string;
  userProbability: number;
  marketImpliedProbability?: number | null;
  snapshotSource?: string;
  outcomeLabel?: string;
  snapshotMetadata?: Record<string, unknown>;
  marketTitle?: string;
  category?: string;
  closeAt?: string;
  mode?: ForecastMode;
  source?: ForecastSource;
};

export type FetchForecastDashboardInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  token: string;
};

export async function createAnonymousForecaster(
  input: CreateAnonymousForecasterInput = {},
): Promise<ForecasterCreateResponse> {
  const apiBase = requireApiBase(input.apiBase ?? API_BASE);
  return fetchJson<ForecasterCreateResponse>(
    input.fetcher ?? fetch,
    `${apiBase}/api/v1/forecasters/anonymous`,
    {
      method: "POST",
    },
  );
}

export async function recoverForecaster(
  input: RecoverForecasterInput,
): Promise<ForecasterCreateResponse> {
  const apiBase = requireApiBase(input.apiBase ?? API_BASE);
  return fetchJson<ForecasterCreateResponse>(
    input.fetcher ?? fetch,
    `${apiBase}/api/v1/forecasters/recover`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ recovery_code: input.recoveryCode }),
    },
  );
}

export async function lockForecast(input: LockForecastInput): Promise<ForecastResponse> {
  const apiBase = requireApiBase(input.apiBase ?? API_BASE);
  const body: Record<string, unknown> = {
    token: input.token,
    url: input.url,
    user_probability: input.userProbability,
    market_implied_probability: input.marketImpliedProbability ?? null,
    snapshot_source: input.snapshotSource ?? "manual",
    mode: input.mode ?? "live",
    source: input.source ?? "web",
  };
  if (input.outcomeLabel !== undefined) {
    body.outcome_label = input.outcomeLabel;
  }
  if (input.snapshotMetadata !== undefined) {
    body.snapshot_metadata = input.snapshotMetadata;
  }
  if (input.marketTitle !== undefined) {
    body.market_title = input.marketTitle;
  }
  if (input.category !== undefined) {
    body.category = input.category;
  }
  if (input.closeAt !== undefined) {
    body.close_at = input.closeAt;
  }

  return fetchJson<ForecastResponse>(input.fetcher ?? fetch, `${apiBase}/api/v1/forecasts`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function fetchForecastDashboard(
  input: FetchForecastDashboardInput,
): Promise<ForecastDashboard> {
  const apiBase = requireApiBase(input.apiBase ?? API_BASE);
  return fetchJson<ForecastDashboard>(
    input.fetcher ?? fetch,
    `${apiBase}/api/v1/forecasters/me/dashboard`,
    {
      cache: "no-store",
      headers: {
        "X-Forecaster-Token": input.token,
      },
    },
  );
}

export async function fetchBackfillMarkets(input: {
  apiBase?: string;
  fetcher?: Fetcher;
} = {}): Promise<BackfillMarket[]> {
  const apiBase = requireApiBase(input.apiBase ?? API_BASE);
  return fetchJson<BackfillMarket[]>(
    input.fetcher ?? fetch,
    `${apiBase}/api/v1/backfill/markets`,
    {
      cache: "no-store",
    },
  );
}

async function fetchJson<T>(fetcher: Fetcher, url: string, init?: RequestInit): Promise<T> {
  const response = await fetcher(url, init);
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return (await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Fall through to status text.
  }
  return response.statusText || `HTTP ${response.status}`;
}

function requireApiBase(value: string): string {
  const apiBase = value.trim().replace(/\/+$/, "");
  if (!apiBase) {
    throw new Error("Backend API URL is not configured.");
  }
  return apiBase;
}
