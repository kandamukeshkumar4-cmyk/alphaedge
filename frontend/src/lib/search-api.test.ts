import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { searchUnified } from "./search-api";

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
