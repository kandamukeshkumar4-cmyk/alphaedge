export type LockForecastPayload = {
  token: string;
  url: string;
  user_probability: number;
  market_implied_probability: number | null;
  snapshot_source: string;
  outcome_label: string;
  snapshot_metadata: Record<string, unknown>;
  market_title?: string;
  category?: string;
  close_at?: string;
  mode: "live" | "practice";
  source: "extension";
};

export type LockForecastMessage = {
  type: "ALPHAEDGE_LOCK_FORECAST";
  endpoint: "/api/v1/forecasts";
  payload: LockForecastPayload;
};

export type ResolveMarketMessage = {
  type: "ALPHAEDGE_RESOLVE_MARKET";
  endpoint: "/api/v1/markets/external/resolve-url";
  payload: {
    url: string;
    title?: string;
  };
};

export type BuildLockForecastMessageInput = {
  token: string;
  url: string;
  userProbability: number;
  marketImpliedProbability?: number | null;
  outcomeLabel: string;
  snapshotMetadata: Record<string, unknown>;
  snapshotSource?: string;
  marketTitle?: string;
  category?: string;
  closeAt?: string;
  mode?: "live" | "practice";
};

export function buildResolveMarketMessage(input: {
  url: string;
  title?: string;
}): ResolveMarketMessage {
  return {
    type: "ALPHAEDGE_RESOLVE_MARKET",
    endpoint: "/api/v1/markets/external/resolve-url",
    payload: {
      url: input.url,
      title: input.title,
    },
  };
}

export function buildLockForecastMessage(
  input: BuildLockForecastMessageInput,
): LockForecastMessage {
  return {
    type: "ALPHAEDGE_LOCK_FORECAST",
    endpoint: "/api/v1/forecasts",
    payload: {
      token: input.token,
      url: input.url,
      user_probability: input.userProbability,
      market_implied_probability: input.marketImpliedProbability ?? null,
      snapshot_source:
        input.snapshotSource ??
        (input.marketImpliedProbability == null ? "server" : "manual"),
      outcome_label: input.outcomeLabel,
      snapshot_metadata: input.snapshotMetadata,
      market_title: input.marketTitle,
      category: input.category,
      close_at: input.closeAt,
      mode: input.mode ?? "live",
      source: "extension",
    },
  };
}

export function isLockForecastMessage(value: unknown): value is LockForecastMessage {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<LockForecastMessage>;
  return candidate.type === "ALPHAEDGE_LOCK_FORECAST" && candidate.endpoint === "/api/v1/forecasts";
}

export function isResolveMarketMessage(value: unknown): value is ResolveMarketMessage {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<ResolveMarketMessage>;
  return (
    candidate.type === "ALPHAEDGE_RESOLVE_MARKET" &&
    candidate.endpoint === "/api/v1/markets/external/resolve-url"
  );
}
