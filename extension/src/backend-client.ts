import type { LockForecastMessage } from "./messaging";
import type { MirrorTelemetryEvent } from "./telemetry";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type ForecasterProfileResponse = {
  id: string;
  token: string;
  recovery_code: string;
  disclaimer: string;
};

export type ForecastLifecycleSummary = {
  unresolved_count: number;
  recently_resolved_count: number;
  unresolved: ForecastLifecycleItem[];
  recently_resolved: ForecastLifecycleItem[];
};

export type ForecastLifecycleItem = {
  forecast_id: string;
  external_market_id: string;
  platform: "polymarket" | "kalshi" | "manual";
  title: string;
  url: string;
  outcome_label: string;
  user_probability: number;
  market_implied_probability: number | null;
  locked_at: string;
  status: string;
  user_brier?: number | null;
  brier_delta?: number | null;
  synthetic_pnl?: number | null;
  resolved_at?: string | null;
};

export type ForecastDashboardSummary = {
  paper_trading_only: boolean;
  live: {
    resolved_count: number;
    unresolved_count: number;
    headline_count?: number;
    independent_count: number;
    anchored_count: number;
    mean_user_brier: number | null;
    mean_brier_delta: number | null;
    synthetic_pnl_total: number;
  };
  brier_trend?: Array<{
    seq: number;
    locked_at: string;
    user_brier: number;
    market_brier: number | null;
  }>;
};

export const SIGNAL_PANEL_DISCLAIMER =
  "Research only — not financial advice. Verify resolution terms. Paper trading only.";

export type ArbitrageSignalResponse = {
  paper_trading_only: boolean;
  disclaimer: string;
  signal?: {
    is_arbitrage?: boolean;
    net_spread?: number;
    return_pct?: number;
    yes_leg?: { market?: { platform?: string; market_id?: string }; outcome?: string; price?: number };
    no_leg?: { market?: { platform?: string; market_id?: string }; outcome?: string; price?: number };
    resolution_status?: string;
    confidence?: number;
  };
};

export type DutchingSignalResponse = {
  paper_trading_only: boolean;
  disclaimer: string;
  signal?: {
    risk_free?: boolean;
    combined_implied?: number;
    total_cost?: number;
    return_pct?: number;
    outcomes?: Array<{ name?: string; price?: number; stake_share?: number }>;
  };
};

export type SmartMoneySignalResponse = {
  paper_trading_only: boolean;
  disclaimer: string;
  platform?: string;
  market_id?: string;
  tracked_holder_count?: number;
  positions?: Array<{
    holder_address?: string;
    side?: string;
    outcome?: string;
    total_pnl?: number;
    roi?: number;
  }>;
};

export type ForecastSignalResponse = {
  paper_trading_only: boolean;
  disclaimer: string;
  platform?: string;
  market_id?: string;
  signal?: {
    model_prob?: number;
    confidence?: number;
    edge?: number;
    is_edge?: boolean;
    clv?: number | null;
    reason?: string;
    trade_count?: number;
  };
};

export type ExternalMarketResolveResponse = {
  id: string;
  platform: "polymarket" | "kalshi" | "manual";
  external_id: string;
  url: string;
  title: string;
  category: string;
  status: string;
  close_at: string | null;
  resolved_at: string | null;
  market_implied_probability?: number | null;
  implied_probability?: number | null;
  snapshot?: {
    implied_probability?: number | null;
    source?: string;
    metadata?: Record<string, unknown>;
    captured_at?: string;
  } | null;
  snapshot_metadata?: Record<string, unknown> | null;
};

export async function createAnonymousForecaster(input: {
  apiBase: string;
  fetcher?: Fetcher;
}): Promise<ForecasterProfileResponse> {
  const fetcher = input.fetcher ?? fetch;
  const response = await fetcher(`${input.apiBase}/api/v1/forecasters/anonymous`, {
    method: "POST",
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as ForecasterProfileResponse;
}

export async function recoverForecaster(input: {
  apiBase: string;
  recoveryCode: string;
  fetcher?: Fetcher;
}): Promise<ForecasterProfileResponse> {
  const fetcher = input.fetcher ?? fetch;
  const response = await fetcher(`${input.apiBase}/api/v1/forecasters/recover`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ recovery_code: input.recoveryCode }),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as ForecasterProfileResponse;
}

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

export async function resolveExternalMarket(input: {
  apiBase: string;
  url: string;
  title?: string;
  fetcher?: Fetcher;
}): Promise<ExternalMarketResolveResponse> {
  const fetcher = input.fetcher ?? fetch;
  const response = await fetcher(`${input.apiBase}/api/v1/markets/external/resolve-url`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      url: input.url,
      ...(input.title ? { title: input.title } : {}),
    }),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as ExternalMarketResolveResponse;
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

export async function fetchForecastDashboard(input: {
  apiBase: string;
  token: string;
  fetcher?: Fetcher;
}): Promise<ForecastDashboardSummary> {
  const fetcher = input.fetcher ?? fetch;
  const response = await fetcher(`${input.apiBase}/api/v1/forecasters/me/dashboard`, {
    cache: "no-store",
    headers: {
      "X-Forecaster-Token": input.token,
    },
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as ForecastDashboardSummary;
}

export async function fetchArbitrageSignal(input: {
  apiBase: string;
  platform: string;
  marketId: string;
  fetcher?: Fetcher;
}): Promise<ArbitrageSignalResponse | null> {
  return fetchSignalEndpoint(input, "arbitrage");
}

export async function fetchDutchingSignal(input: {
  apiBase: string;
  platform: string;
  marketId: string;
  fetcher?: Fetcher;
}): Promise<DutchingSignalResponse | null> {
  return fetchSignalEndpoint(input, "dutching");
}

export async function fetchSmartMoneySignal(input: {
  apiBase: string;
  platform: string;
  marketId: string;
  fetcher?: Fetcher;
}): Promise<SmartMoneySignalResponse | null> {
  const raw = await fetchSignalEndpoint<{
    paper_trading_only: boolean;
    disclaimer: string;
    platform?: string;
    market_id?: string;
    tracked_wallet_count?: number;
    positions?: Array<{
      wallet_address?: string;
      side?: string;
      outcome?: string;
      total_pnl?: number;
      roi?: number;
    }>;
  }>(input, "smart-money");
  if (!raw) {
    return null;
  }
  return {
    paper_trading_only: raw.paper_trading_only,
    disclaimer: raw.disclaimer,
    platform: raw.platform,
    market_id: raw.market_id,
    tracked_holder_count: raw.tracked_wallet_count,
    positions: (raw.positions ?? []).map((position) => ({
      holder_address: position.wallet_address,
      side: position.side,
      outcome: position.outcome,
      total_pnl: position.total_pnl,
      roi: position.roi,
    })),
  };
}

export async function fetchForecastSignal(input: {
  apiBase: string;
  platform: string;
  marketId: string;
  fetcher?: Fetcher;
}): Promise<ForecastSignalResponse | null> {
  return fetchSignalEndpoint(input, "forecast");
}

async function fetchSignalEndpoint<T>(
  input: { apiBase: string; platform: string; marketId: string; fetcher?: Fetcher },
  kind: "arbitrage" | "dutching" | "smart-money" | "forecast",
): Promise<T | null> {
  const fetcher = input.fetcher ?? fetch;
  const params = new URLSearchParams({
    platform: input.platform,
    market_id: input.marketId,
  });
  const response = await fetcher(
    `${input.apiBase}/api/v1/signals/${kind}?${params.toString()}`,
    { cache: "no-store" },
  );
  if (response.status === 404) {
    return null;
  }
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as T;
}

export async function recordMirrorTelemetryEvent(input: {
  apiBase: string;
  event: MirrorTelemetryEvent;
  token?: string;
  fetcher?: Fetcher;
}): Promise<{ ok: true; event_id: string }> {
  const fetcher = input.fetcher ?? fetch;
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (input.token) {
    headers["X-Forecaster-Token"] = input.token;
  }
  const response = await fetcher(`${input.apiBase}/api/v1/telemetry/mirror/events`, {
    method: "POST",
    headers,
    body: JSON.stringify(input.event),
  });
  const data = await safeJson(response);
  if (!response.ok) {
    throw new Error(detailFrom(data) ?? `HTTP ${response.status}`);
  }
  return data as { ok: true; event_id: string };
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
