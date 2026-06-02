import { describe, expect, it } from "vitest";

import { mergeApiSnapshotForDetail } from "./api-market-detail-adapter";
import { MARKETS } from "./mock-data";
import type { MarketSnapshot } from "./market-view-model";

const snapshot: MarketSnapshot = {
  paper_trading_only: true,
  disclaimer: "This project is a paper-trading simulation for sports and election markets.",
  market: {
    id: "11111111-1111-1111-1111-111111111111",
    slug: "elect-la-mayor-2026",
    title: "Los Angeles mayoral election API",
    question: "Will the incumbent win re-election?",
    category: "Politics",
    icon: "🗳️",
    volume: 842000,
    traders: 1104,
    market_count: 1,
    description: "API detail description.",
    resolution: "Resolves to the certified winner of the election.",
    status: "open",
    lock_at: "2026-07-02T21:38:48Z",
    resolved_at: null,
    winning_outcome: null,
  },
  book: {
    yes: {
      bids: [{ price: 0.63, size: 120 }],
      asks: [{ price: 0.66, size: 240 }],
    },
    no: {
      bids: [{ price: 0.34, size: 180 }],
      asks: [{ price: 0.37, size: 260 }],
    },
  },
  activity: [],
  forecast: {
    predicted_prob: 0.68,
    confidence: 0.81,
    edge_vs_book: 0.02,
    input_feature_hash: "api-fixture",
  },
  evaluation: {
    latest_brier_score: 0.142,
    predicted_prob: 0.68,
    actual_outcome: 1,
    closing_implied: 0.66,
  },
};

describe("api market detail adapter", () => {
  it("overlays API snapshot proof onto an existing local detail market", () => {
    const market = mergeApiSnapshotForDetail(snapshot, MARKETS);

    expect(market.title).toBe("Los Angeles mayoral election API");
    expect(market.category).toBe("Politics");
    expect(market.icon).toBe("🗳️");
    expect(market.description).toBe("API detail description.");
    expect(market.bids[0]).toEqual({ price: 0.63, size: 120 });
    expect(market.asks[0]).toEqual({ price: 0.66, size: 240 });
    expect(market.forecast).toMatchObject({
      prob: 0.68,
      confidence: 0.81,
      edge: 0.02,
      brier: 0.142,
    });
  });

  it("creates a usable binary detail market for an API-only election snapshot", () => {
    const market = mergeApiSnapshotForDetail(
      {
        ...snapshot,
        market: {
          ...snapshot.market,
          id: "22222222-2222-2222-2222-222222222222",
          slug: "elect-senate-control-2026",
          title: "Senate control after 2026",
        },
      },
      MARKETS,
    );

    expect(market.slug).toBe("elect-senate-control-2026");
    expect(market.outcomes.map((outcome) => outcome.label)).toEqual(["YES", "NO"]);
    expect(market.trades).toEqual([]);
    expect(market.holders).toEqual([]);
    expect(market.comments).toEqual([]);
  });
});
