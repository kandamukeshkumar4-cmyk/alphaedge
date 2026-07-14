import { describe, expect, it } from "vitest";

import { activeTrendingMarkets } from "./live-discovery";
import { MARKETS, type Market } from "./mock-data";

function market(overrides: Partial<Market>): Market {
  return {
    ...MARKETS[0],
    id: overrides.id ?? crypto.randomUUID(),
    slug: overrides.slug ?? crypto.randomUUID(),
    title: overrides.title ?? "Test market",
    status: "open",
    endsAt: "2099-01-01T00:00:00Z",
    outcomes: [
      { ...MARKETS[0].outcomes[0], price: 0.5 },
      { ...MARKETS[0].outcomes[1], price: 0.5 },
    ],
    ...overrides,
  };
}

describe("activeTrendingMarkets", () => {
  it("preserves backend activity order instead of re-sorting by lifetime volume", () => {
    const recentMover = market({ slug: "recent", volume: 10 });
    const lifetimeVolume = market({ slug: "lifetime", volume: 1_000_000 });

    expect(activeTrendingMarkets([recentMover, lifetimeVolume]).map((m) => m.slug)).toEqual([
      "recent",
      "lifetime",
    ]);
  });

  it("excludes resolved, past-close, and decided-price markets", () => {
    const open = market({ slug: "open" });
    const resolved = market({ slug: "resolved", status: "resolved" });
    const pastClose = market({ slug: "past", endsAt: "2020-01-01T00:00:00Z" });
    const zero = market({
      slug: "zero",
      outcomes: [
        { ...MARKETS[0].outcomes[0], price: 0.01 },
        { ...MARKETS[0].outcomes[1], price: 0.99 },
      ],
    });
    const certain = market({
      slug: "certain",
      outcomes: [
        { ...MARKETS[0].outcomes[0], price: 0.99 },
        { ...MARKETS[0].outcomes[1], price: 0.01 },
      ],
    });

    expect(
      activeTrendingMarkets([resolved, pastClose, zero, certain, open], Date.parse("2026-07-13T00:00:00Z"))
        .map((m) => m.slug),
    ).toEqual(["open"]);
  });
});
