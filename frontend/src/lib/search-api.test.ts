import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { searchMarkets, searchUnified } from "./search-api";

const RESULT = {
  slug: "nba-2025-01-15-lal-bos",
  title: "Lakers vs Celtics",
  platform: "AlphaEdge",
  category: "sports",
  market_type: "prediction",
  yes_price: 0.64,
  volume: 1000,
  status: "open",
};

describe("searchUnified", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("queries GET /api/v1/search with q and limit", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [RESULT],
    } as Response);

    const results = await searchUnified("Lakers", 5);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const href = fetchMock.mock.calls[0][0] as string;
    expect(href).toBe("http://api.test/api/v1/search?q=Lakers&limit=5");
    expect(results).toEqual([RESULT]);
  });

  it("returns [] for blank queries without hitting the network", async () => {
    expect(await searchUnified("")).toEqual([]);
    expect(await searchUnified("   ")).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("trims the query before sending", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    } as Response);

    await searchUnified("  Lakers  ");
    const href = fetchMock.mock.calls[0][0] as string;
    expect(href).toContain("q=Lakers");
  });

  it("throws on HTTP errors so callers can show an honest error state", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 429 } as Response);
    await expect(searchUnified("Lakers")).rejects.toThrow("Search HTTP 429");
  });
});

describe("searchMarkets (V91 SU1 — frozen contract, live-first + mock fallback)", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("normalizes the frozen {items,total,query} envelope from the live API", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [
          {
            slug: "nba-2025-01-15-lal-bos",
            title: "Lakers vs Celtics — Jan 15 Tip-Off",
            category: "NBA",
            icon: "🏀",
            volume: 48_200,
            yes_price: 0.52,
            hours_to_close: 6,
          },
        ],
        total: 1,
        query: "lakers",
      }),
    } as Response);

    const result = await searchMarkets("lakers", 20);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://api.test/api/v1/search?q=lakers&limit=20",
    );
    expect(result.source).toBe("live");
    expect(result.total).toBe(1);
    expect(result.query).toBe("lakers");
    expect(result.items).toEqual([
      {
        slug: "nba-2025-01-15-lal-bos",
        title: "Lakers vs Celtics — Jan 15 Tip-Off",
        category: "NBA",
        icon: "🏀",
        volume: 48_200,
        yes_price: 0.52,
        hours_to_close: 6,
      },
    ]);
  });

  it("returns an empty result for a blank query without hitting the network", async () => {
    const result = await searchMarkets("   ");

    expect(result).toEqual({ items: [], total: 0, query: "", source: "mock" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("falls back to the PAPER mock catalog when the live API is down", async () => {
    fetchMock.mockRejectedValue(new Error("ECONNREFUSED"));

    const result = await searchMarkets("Lakers", 5);

    expect(result.source).toBe("mock");
    expect(result.query).toBe("Lakers");
    expect(result.items.length).toBeGreaterThan(0);
    expect(result.items[0]?.slug).toBe("nba-2025-01-15-lal-bos");
    // Every mock row satisfies the frozen item shape.
    for (const item of result.items) {
      expect(Object.keys(item).sort()).toEqual([
        "category",
        "hours_to_close",
        "icon",
        "slug",
        "title",
        "volume",
        "yes_price",
      ]);
    }
  });
});
