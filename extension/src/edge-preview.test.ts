import { describe, expect, it } from "vitest";

import { buildEdgePreview, shouldPromptForReforecast, timeToCloseBucket } from "./edge-preview";

describe("live edge preview", () => {
  const now = new Date("2026-06-04T12:00:00.000Z");

  it("shows delta, independent status, timing bucket, and paper frame while dragging", () => {
    const preview = buildEdgePreview({
      userProbability: 0.64,
      marketImpliedProbability: 0.55,
      closeAt: "2026-06-04T20:00:00.000Z",
      now,
    });

    expect(preview.delta).toBe(0.09);
    expect(preview.deltaLabel).toBe("+9.0 pts vs market implied");
    expect(preview.anchored).toBe(false);
    expect(preview.anchoringLabel).toBe("Independent edge candidate for post-resolution scoring.");
    expect(preview.timeBucket).toBe("6-24h");
    expect(preview.paperPnlLabel).toBe("Paper 1-unit frame: YES-side score at 55.0 pts implied.");
  });

  it("flags forecasts within 0.02 of market implied as anchored", () => {
    const preview = buildEdgePreview({
      userProbability: 0.52,
      marketImpliedProbability: 0.5,
      closeAt: "2026-06-04T13:30:00.000Z",
      now,
    });

    expect(preview.anchored).toBe(true);
    expect(preview.anchoringLabel).toBe(
      "Anchored: counts for participation, not independent edge.",
    );
    expect(preview.timeBucket).toBe("1-6h");
    expect(preview.paperPnlLabel).toBe(
      "Paper 1-unit frame: anchored forecasts carry no independent P&L signal.",
    );
  });

  it("degrades cleanly when market implied probability is unavailable", () => {
    const preview = buildEdgePreview({
      userProbability: 0.41,
      marketImpliedProbability: null,
      now,
    });

    expect(preview.delta).toBeNull();
    expect(preview.anchored).toBe(false);
    expect(preview.timeBucket).toBe("unknown");
    expect(preview.paperPnlLabel).toContain("after a market-implied probability is available");
  });

  it("matches scoring timing buckets", () => {
    expect(timeToCloseBucket("2026-06-12T12:00:00.000Z", now)).toBe("7d+");
    expect(timeToCloseBucket("2026-06-08T12:00:00.000Z", now)).toBe("1-7d");
    expect(timeToCloseBucket("2026-06-05T00:00:00.000Z", now)).toBe("6-24h");
    expect(timeToCloseBucket("2026-06-04T15:00:00.000Z", now)).toBe("1-6h");
    expect(timeToCloseBucket("2026-06-04T12:45:00.000Z", now)).toBe("<1h");
  });

  it("prompts for a final append-only read close to market close", () => {
    expect(shouldPromptForReforecast("7d+")).toBe(false);
    expect(shouldPromptForReforecast("1-7d")).toBe(false);
    expect(shouldPromptForReforecast("6-24h")).toBe(false);
    expect(shouldPromptForReforecast("1-6h")).toBe(true);
    expect(shouldPromptForReforecast("<1h")).toBe(true);
  });
});
