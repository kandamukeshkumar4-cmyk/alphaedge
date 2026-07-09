import { describe, expect, it } from "vitest";

import {
  buildMarketDetailView,
  buildTradeTicketPreview,
  formatMultiplier,
  formatProbability,
  type MarketSnapshot,
} from "./market-view-model";

const snapshot: MarketSnapshot = {
  paper_trading_only: true,
  disclaimer:
    "This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only.",
  market: {
    id: "11111111-1111-1111-1111-111111111111",
    slug: "nba-2025-01-15-lal-bos",
    title: "Lakers vs Celtics",
    question: "Will the Lakers win?",
    category: "Sports",
    icon: "🏀",
    volume: 2_413_000,
    traders: 3_214,
    market_count: 3,
    description: "Head-to-head paper market on the Lakers vs Celtics matchup.",
    resolution: "Resolves YES if the Lakers win the game, otherwise NO.",
    status: "open",
    lock_at: "2025-01-15T19:30:00Z",
    resolved_at: null,
    winning_outcome: null,
  },
  book: {
    yes: {
      bids: [{ price: 0.6, size: 20 }],
      asks: [{ price: 0.64, size: 30 }],
    },
    no: {
      bids: [{ price: 0.34, size: 15 }],
      asks: [{ price: 0.36, size: 24 }],
    },
  },
  activity: [
    {
      id: "22222222-2222-2222-2222-222222222222",
      outcome: "yes",
      price: 0.64,
      quantity: 10,
      created_at: "2026-06-02T17:00:00Z",
    },
  ],
  forecast: {
    predicted_prob: 0.68,
    confidence: 0.84,
    edge_vs_book: 0.04,
    input_feature_hash: "fixture-v1",
  },
  evaluation: {
    latest_brier_score: 0.1024,
    predicted_prob: 0.68,
    actual_outcome: 1,
    closing_implied: 0.64,
  },
};

describe("market view model", () => {
  it("formats probabilities and multipliers for market rows", () => {
    expect(formatProbability(0.64)).toBe("64%");
    expect(formatMultiplier(0.64)).toBe("1.56x");
  });

  it("builds a paper-only market detail model with AI edge and book summaries", () => {
    const detail = buildMarketDetailView(snapshot);

    expect(detail.title).toBe("Lakers vs Celtics");
    expect(detail.statusLabel).toBe("Open");
    expect(detail.primaryPriceLabel).toBe("64%");
    expect(detail.outcomes[0]).toMatchObject({
      label: "YES",
      bestPriceLabel: "64%",
      multiplierLabel: "1.56x",
    });
    expect(detail.forecast).toMatchObject({
      probabilityLabel: "68%",
      confidenceLabel: "84%",
      edgeLabel: "+4%",
      verdict: "Positive model edge",
    });
    expect(detail.activity[0].summary).toBe("YES filled at 64% for 10 shares");
    expect(detail.paperOnlyLabel).toBe("Research only");
  });

  it("previews cost, payout, and remaining paper balance", () => {
    const preview = buildTradeTicketPreview({
      price: 0.64,
      shares: 10,
      balance: 100_000,
    });

    expect(preview.costLabel).toBe("$6.40");
    expect(preview.toWinLabel).toBe("$10.00");
    expect(preview.potentialProfitLabel).toBe("+$3.60");
    expect(preview.balanceAfterLabel).toBe("$99,993.60");
  });
});
