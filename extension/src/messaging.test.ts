import { describe, expect, it } from "vitest";

import {
  buildLockForecastMessage,
  buildResolveMarketMessage,
  isLockForecastMessage,
  isResolveMarketMessage,
} from "./messaging";

describe("extension message passing", () => {
  it("builds a lock-forecast message that can only target the forecast API", () => {
    const message = buildLockForecastMessage({
      token: "forecaster-token",
      url: "https://polymarket.com/event/will-it-rain-2026",
      userProbability: 0.64,
      marketImpliedProbability: null,
      outcomeLabel: "YES",
      snapshotSource: "polymarket.gamma",
      snapshotMetadata: { provider: "polymarket" },
      category: "Weather",
      closeAt: "2026-06-10T20:00:00Z",
    });

    expect(message.type).toBe("ALPHAEDGE_LOCK_FORECAST");
    expect(message.endpoint).toBe("/api/v1/forecasts");
    expect(message.payload).toMatchObject({
      source: "extension",
      user_probability: 0.64,
      outcome_label: "YES",
      snapshot_source: "polymarket.gamma",
      category: "Weather",
      close_at: "2026-06-10T20:00:00Z",
    });
    expect(isLockForecastMessage(message)).toBe(true);
    expect(isLockForecastMessage({ type: "PLACE_ORDER", endpoint: "/orders" })).toBe(false);
  });

  it("builds a resolve-url message for service-worker prefill only", () => {
    const message = buildResolveMarketMessage({
      url: "https://kalshi.com/markets/fed/fed-26jun",
      title: "Fed decision",
    });

    expect(message).toEqual({
      type: "ALPHAEDGE_RESOLVE_MARKET",
      endpoint: "/api/v1/markets/external/resolve-url",
      payload: {
        url: "https://kalshi.com/markets/fed/fed-26jun",
        title: "Fed decision",
      },
    });
    expect(isResolveMarketMessage(message)).toBe(true);
    expect(isResolveMarketMessage({ type: "ALPHAEDGE_RESOLVE_MARKET", endpoint: "/api/v1/forecasts" })).toBe(false);
  });
});
