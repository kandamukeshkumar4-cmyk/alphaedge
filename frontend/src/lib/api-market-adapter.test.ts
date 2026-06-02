import { describe, expect, it } from "vitest";

import { mergeApiMarketsForCards, type ApiMarketCatalogItem } from "./api-market-adapter";
import { MARKETS } from "./mock-data";

const baseApiMarket: ApiMarketCatalogItem = {
  id: "11111111-1111-1111-1111-111111111111",
  slug: "nba-2025-01-15-lal-bos",
  title: "Lakers vs Celtics API",
  question: "Will the Lakers win?",
  status: "open",
  lock_at: "2026-06-02T23:00:00Z",
  resolved_at: null,
  winning_outcome: null,
  category: "Sports",
  icon: "basketball",
  volume: 2_413_000,
  traders: 3_214,
  market_count: 3,
  description: "API-backed Lakers market.",
  resolution: "Resolves YES if the Lakers win.",
};

describe("api market adapter", () => {
  it("merges API catalog metadata into existing card-ready mock markets", () => {
    const [merged] = mergeApiMarketsForCards([baseApiMarket], MARKETS);

    expect(merged.slug).toBe("nba-2025-01-15-lal-bos");
    expect(merged.title).toBe("Lakers vs Celtics API");
    expect(merged.category).toBe("Sports");
    expect(merged.icon).toBe("basketball");
    expect(merged.description).toBe("API-backed Lakers market.");
    expect(merged.outcomes[0].label).toBe("Lakers");
  });

  it("creates a card-ready election market when the API has no local mock match", () => {
    const [market] = mergeApiMarketsForCards(
      [
        {
          ...baseApiMarket,
          id: "22222222-2222-2222-2222-222222222222",
          slug: "elect-senate-control-2026",
          title: "Senate control after 2026",
          question: "Will Democrats control the Senate after the 2026 election?",
          category: "Politics",
          icon: "ballot",
          volume: 842_000,
          traders: 1_104,
          market_count: 1,
          description: "Paper market on the certified Los Angeles mayoral result.",
          resolution: "Resolves to the certified winner of the election.",
        },
      ],
      MARKETS,
    );

    expect(market.slug).toBe("elect-senate-control-2026");
    expect(market.category).toBe("Politics");
    expect(market.outcomes.map((outcome) => outcome.label)).toEqual(["YES", "NO"]);
    expect(market.forecast.confidence).toBeGreaterThanOrEqual(0.7);
  });
});
