import { describe, expect, it } from "vitest";

import {
  isKalshiMatchCard,
  isKalshiWcMatchSlug,
  pickHomeGridMarkets,
} from "./hero-market";
import type { Market } from "./mock-data";

function kalshiLeg(
  slug: string,
  title: string,
  label: string,
  price: number,
  volume: number,
): Market {
  return {
    id: slug,
    slug,
    category: "Sports",
    icon: "⚽",
    title,
    question: `${label} — ${title}`,
    endsAt: "2026-06-27T22:00:00Z",
    volume,
    traders: 0,
    marketCount: 3,
    trendDelta: 0,
    source: "kalshi",
    outcomes: [
      {
        id: "yes",
        label: "YES",
        emoji: "⚽",
        price,
        prevPrice: price,
        tone: "primary",
      },
      {
        id: "no",
        label: "NO",
        emoji: "✕",
        price: 1 - price,
        prevPrice: 1 - price,
        tone: "danger",
      },
    ],
    forecast: { prob: price, confidence: 0.5, edge: 0, brier: 0.2, reasoning: "" },
    bids: [],
    asks: [],
    description: "",
    resolution: "",
    trades: [],
    holders: [],
    comments: [],
    seed: 1,
  };
}

describe("hero-market grid helpers", () => {
  it("detects Kalshi WC match slugs", () => {
    expect(isKalshiWcMatchSlug("ks-kxwcgame-26jun13bramar-bra")).toBe(true);
    expect(isKalshiWcMatchSlug("pm-will-brazil-win")).toBe(false);
  });

  it("groups ks-kxwcgame legs into one match card per event", () => {
    const all = [
      kalshiLeg("ks-kxwcgame-26jun13bramar-bra", "Brazil vs Morocco", "Brazil", 0.59, 1_500_000),
      kalshiLeg("ks-kxwcgame-26jun13bramar-mar", "Brazil vs Morocco", "Morocco", 0.18, 900_000),
      kalshiLeg("ks-kxwcgame-26jun13bramar-tie", "Brazil vs Morocco", "Tie", 0.24, 800_000),
      kalshiLeg("ks-kxwcgame-26jun12canbih-can", "Canada vs Bosnia", "Canada", 0.54, 2_000_000),
      kalshiLeg("ks-kxwcgame-26jun12canbih-bih", "Canada vs Bosnia", "Bosnia", 0.2, 700_000),
      kalshiLeg("ks-kxwcgame-26jun12canbih-tie", "Canada vs Bosnia", "Tie", 0.27, 600_000),
      kalshiLeg(
        "pm-will-south-korea-win-the-2026-fifa-world-cup-485",
        "Will South Korea win the 2026 FIFA World Cup?",
        "YES",
        0.004,
        60_000_000,
      ),
    ];

    const grid = pickHomeGridMarkets(all);
    expect(grid).toHaveLength(2);
    expect(grid.every((m) => m.outcomes.length >= 3)).toBe(true);
    expect(grid.some((m) => m.title === "Brazil vs Morocco")).toBe(true);
    expect(grid.some((m) => m.slug.includes("south-korea"))).toBe(false);
    expect(isKalshiMatchCard(grid[0])).toBe(true);
  });
});
