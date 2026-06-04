import { describe, expect, it } from "vitest";

import { parseSupportedUrl } from "./platforms";

describe("platform URL parsing", () => {
  it("parses Polymarket event URLs without query tracking", () => {
    expect(
      parseSupportedUrl("https://polymarket.com/event/will-it-rain-2026?tid=123"),
    ).toEqual({
      platform: "polymarket",
      provider: "polymarket",
      externalId: "will-it-rain-2026",
      canonicalUrl: "https://polymarket.com/event/will-it-rain-2026",
      manualOnly: false,
      title: "",
    });
  });

  it("parses Kalshi market URLs", () => {
    expect(parseSupportedUrl("https://kalshi.com/markets/RAIN/rain-nyc")).toMatchObject({
      platform: "kalshi",
      provider: "kalshi",
      externalId: "rain/rain-nyc",
      canonicalUrl: "https://kalshi.com/markets/rain/rain-nyc",
      manualOnly: false,
    });
  });

  it("keeps FanDuel manual-only and never extracts odds from the DOM", () => {
    expect(
      parseSupportedUrl("https://sportsbook.fanduel.com/navigation/nba", "Lakers vs Celtics"),
    ).toEqual({
      platform: "manual",
      provider: "fanduel",
      externalId: "fanduel:sportsbook.fanduel.com/navigation/nba",
      canonicalUrl: "https://sportsbook.fanduel.com/navigation/nba",
      manualOnly: true,
      title: "Lakers vs Celtics",
    });
  });
});
