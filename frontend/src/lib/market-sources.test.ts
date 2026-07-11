import { describe, expect, it } from "vitest";
import type { Market } from "./mock-data";
import {
  isKalshiSource,
  isPolymarketSource,
  filterKalshiMarkets,
  filterPolymarketMarkets,
} from "./market-sources";

function market(overrides: Partial<Market>): Market {
  return { slug: "x", source: undefined, ...overrides } as Market;
}

describe("isKalshiSource", () => {
  it("matches an explicit kalshi source (case-insensitive)", () => {
    expect(isKalshiSource(market({ source: "Kalshi" }))).toBe(true);
  });

  it("matches a ks- slug prefix even without a source", () => {
    expect(isKalshiSource(market({ slug: "ks-foo" }))).toBe(true);
  });

  it("rejects a polymarket market", () => {
    expect(isKalshiSource(market({ source: "polymarket", slug: "pm-bar" }))).toBe(
      false,
    );
  });
});

describe("isPolymarketSource", () => {
  it("matches an explicit polymarket source", () => {
    expect(isPolymarketSource(market({ source: "POLYMARKET" }))).toBe(true);
  });

  it("matches a pm- slug prefix", () => {
    expect(isPolymarketSource(market({ slug: "pm-foo" }))).toBe(true);
  });

  it("rejects a kalshi market", () => {
    expect(isPolymarketSource(market({ source: "kalshi", slug: "ks-x" }))).toBe(
      false,
    );
  });
});

describe("filters", () => {
  const markets: Market[] = [
    market({ slug: "ks-1", source: "kalshi" }),
    market({ slug: "pm-1", source: "polymarket" }),
    market({ slug: "seed-1", source: undefined }),
  ];

  it("filterKalshiMarkets keeps only kalshi rows", () => {
    expect(filterKalshiMarkets(markets).map((m) => m.slug)).toEqual(["ks-1"]);
  });

  it("filterPolymarketMarkets keeps only polymarket rows", () => {
    expect(filterPolymarketMarkets(markets).map((m) => m.slug)).toEqual(["pm-1"]);
  });
});
