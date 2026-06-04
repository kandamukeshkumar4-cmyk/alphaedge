import { describe, expect, it } from "vitest";

import { buildLockForecastMessage } from "./messaging";
import { buildForecastReceipt } from "./receipt";

describe("forecast receipt", () => {
  it("includes timestamp, platform, market, probabilities, and lock status without token values", () => {
    const receipt = buildForecastReceipt({
      message: buildLockForecastMessage({
        token: "secret-token",
        url: "https://polymarket.com/event/will-fed-cut-rates-in-july",
        userProbability: 0.64,
        marketImpliedProbability: null,
        outcomeLabel: "YES",
        marketTitle: "Will the Fed cut rates in July?",
        snapshotMetadata: { provider: "polymarket" },
      }),
      lockedAt: "2026-06-04T15:00:00.000Z",
      platform: "polymarket",
      status: "queued",
    });

    expect(receipt).toContain("Locked at: 2026-06-04T15:00:00.000Z");
    expect(receipt).toContain("Platform: polymarket");
    expect(receipt).toContain("Market: Will the Fed cut rates in July?");
    expect(receipt).toContain("User probability: 64.0%");
    expect(receipt).toContain("Implied probability: server snapshot");
    expect(receipt).toContain("Status: queued");
    expect(receipt).not.toContain("secret-token");
  });
});
