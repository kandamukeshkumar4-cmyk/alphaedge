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
  mode: "live" | "practice";
  source: "extension";
};

export type LockForecastMessage = {
  type: "ALPHAEDGE_LOCK_FORECAST";
  endpoint: "/api/v1/forecasts";
  payload: LockForecastPayload;
};

export type BuildLockForecastMessageInput = {
  token: string;
  url: string;
  userProbability: number;
  marketImpliedProbability?: number | null;
  outcomeLabel: string;
  snapshotMetadata: Record<string, unknown>;
  marketTitle?: string;
  category?: string;
  mode?: "live" | "practice";
};

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
      snapshot_source: input.marketImpliedProbability === null ? "server" : "manual",
      outcome_label: input.outcomeLabel,
      snapshot_metadata: input.snapshotMetadata,
      market_title: input.marketTitle,
      category: input.category,
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
