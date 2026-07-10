import { describe, expect, it } from "vitest";
import { FIRST_BET_STEPS, pickSuggestedMarket } from "./onboarding-first-bet";
import type { Market } from "./mock-data";

function mkt(overrides: Partial<Market>): Market {
  return {
    id: overrides.slug ?? "m",
    slug: "m",
    category: "Sports",
    icon: "",
    title: "Market",
    question: "",
    endsAt: "",
    volume: 0,
    traders: 0,
    marketCount: 1,
    trendDelta: 0,
    outcomes: [],
    forecast: {} as Market["forecast"],
    bids: [],
    asks: [],
    description: "",
    resolution: "",
    trades: [],
    holders: [],
    comments: [],
    seed: 0,
    ...overrides,
  };
}

describe("pickSuggestedMarket", () => {
  it("returns null with no markets", () => {
    expect(pickSuggestedMarket([])).toBeNull();
  });

  it("picks the highest-volume open market", () => {
    const picked = pickSuggestedMarket([
      mkt({ slug: "a", volume: 100 }),
      mkt({ slug: "b", volume: 900 }),
      mkt({ slug: "c", volume: 500 }),
    ]);
    expect(picked?.slug).toBe("b");
  });

  it("excludes locked and resolved markets", () => {
    const picked = pickSuggestedMarket([
      mkt({ slug: "big", volume: 9999, status: "resolved" }),
      mkt({ slug: "locked", volume: 8888, status: "locked" }),
      mkt({ slug: "open", volume: 10, status: "open" }),
    ]);
    expect(picked?.slug).toBe("open");
  });

  it("treats undefined status as open", () => {
    expect(pickSuggestedMarket([mkt({ slug: "x", volume: 1 })])?.slug).toBe("x");
  });
});

describe("FIRST_BET_STEPS", () => {
  it("is the three guided steps in order", () => {
    expect(FIRST_BET_STEPS.map((s) => s.key)).toEqual(["price", "edge", "trade"]);
  });
});
