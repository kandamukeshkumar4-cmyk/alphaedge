import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchCatalogMarketForDetail,
  mergeApiDetailForCards,
  type MarketDetailApi,
} from "./alphaedge-api";
import { MARKETS } from "./mock-data";

const DETAIL: MarketDetailApi = {
  slug: "elect-la-mayor-2026",
  title: "Los Angeles mayoral election",
  category: "Politics",
  status: "open",
  outcomes: [
    { label: "YES", implied_prob: 0.66, price: 0.66 },
    { label: "NO", implied_prob: 0.34, price: 0.34 },
  ],
  forecast: null,
  volume_usd: 1_000,
  traders: 10,
  resolution_criteria: "Resolves from the certified result.",
  paper_trading_only: true,
  resolved: false,
  resolution_outcome: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("market detail lifecycle metadata", () => {
  it("fetches the existing catalog row as the real close-time source", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "market-id",
        slug: DETAIL.slug,
        title: DETAIL.title,
        question: DETAIL.title,
        status: "open",
        lock_at: "2026-08-14T00:00:00Z",
        resolved_at: null,
        winning_outcome: null,
        category: "Politics",
        icon: "ballot",
        volume: 1_000,
        traders: 10,
        market_count: 1,
        description: "API market",
        resolution: DETAIL.resolution_criteria,
        yes_price: 0.66,
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const market = await fetchCatalogMarketForDetail(DETAIL.slug, "https://api.test");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.test/api/v1/markets/elect-la-mayor-2026",
      { cache: "no-store" },
    );
    expect(market?.endsAt).toBe("2026-08-14T00:00:00Z");
  });

  it("never falls back to a stale bundled close date when catalog evidence is absent", () => {
    const market = mergeApiDetailForCards(DETAIL, []);
    const staleLocal = MARKETS.find((item) => item.slug === DETAIL.slug);

    expect(staleLocal).toBeDefined();
    expect(market.endsAt).toBe("");
    expect(market.status).toBe("open");
  });

  it("keeps a successful catalog row with null lock_at explicitly unknown", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "market-id",
          slug: DETAIL.slug,
          title: DETAIL.title,
          question: DETAIL.title,
          status: "open",
          lock_at: null,
          resolved_at: null,
          winning_outcome: null,
          category: "Politics",
          icon: "ballot",
          volume: 1_000,
          traders: 10,
          market_count: 1,
          description: "API market",
          resolution: DETAIL.resolution_criteria,
          yes_price: 0.66,
        }),
      } as Response),
    );

    const market = await fetchCatalogMarketForDetail(DETAIL.slug, "https://api.test");

    expect(market?.endsAt).toBe("");
    expect(market?.status).toBe("open");
  });
});
