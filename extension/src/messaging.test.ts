import { describe, expect, it } from "vitest";

import { buildLockForecastMessage, isLockForecastMessage } from "./messaging";

describe("extension message passing", () => {
  it("builds a lock-forecast message that can only target the forecast API", () => {
    const message = buildLockForecastMessage({
      token: "forecaster-token",
      url: "https://polymarket.com/event/will-it-rain-2026",
      userProbability: 0.64,
      marketImpliedProbability: null,
      outcomeLabel: "YES",
      snapshotMetadata: { provider: "polymarket" },
    });

    expect(message.type).toBe("ALPHAEDGE_LOCK_FORECAST");
    expect(message.endpoint).toBe("/api/v1/forecasts");
    expect(message.payload).toMatchObject({
      source: "extension",
      user_probability: 0.64,
      outcome_label: "YES",
    });
    expect(isLockForecastMessage(message)).toBe(true);
    expect(isLockForecastMessage({ type: "PLACE_ORDER", endpoint: "/orders" })).toBe(false);
  });
});
