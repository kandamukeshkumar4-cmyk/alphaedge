import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { __clearMarketsCache, fetchMarkets } from "./alphaedge-api";

const API_MARKET = {
  slug: "nba-2025-01-15-lal-bos",
  title: "Lakers vs Celtics",
  category: "sports",
  status: "open",
  yes_price: 0.64,
  no_price: 0.36,
  volume: 1000,
  traders: 10,
  close_time: "2026-01-15T00:00:00Z",
};

function okResponse() {
  return {
    ok: true,
    status: 200,
    json: async () => [API_MARKET],
  } as Response;
}

describe("fetchMarkets shared cache", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers();
    fetchMock.mockReset();
    __clearMarketsCache();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("coalesces concurrent identical calls into one request", async () => {
    fetchMock.mockResolvedValue(okResponse());
    const [a, b, c] = await Promise.all([
      fetchMarkets({}),
      fetchMarkets({}),
      fetchMarkets({}),
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(a).toEqual(b);
    expect(b).toEqual(c);
  });

  it("serves from cache within the TTL and refetches after it expires", async () => {
    fetchMock.mockResolvedValue(okResponse());
    await fetchMarkets({});
    await fetchMarkets({});
    expect(fetchMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(4100);
    await fetchMarkets({});
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("keys the cache by filter params", async () => {
    fetchMock.mockResolvedValue(okResponse());
    await fetchMarkets({});
    await fetchMarkets({ category: "sports" });
    await fetchMarkets({ sort: "volume" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("sends the additive active sort to the market catalog", async () => {
    fetchMock.mockResolvedValue(okResponse());
    await fetchMarkets({ sort: "active" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/markets?sort=active",
      { cache: "no-store" },
    );
  });

  it("does not cache failures", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    fetchMock.mockResolvedValueOnce({ ok: false, status: 429 } as Response);
    // Soft-fail: resolve empty so header/ticker probes never throw pageerrors.
    await expect(fetchMarkets({})).resolves.toEqual([]);
    expect(warn).toHaveBeenCalledWith(
      "Markets HTTP 429 — using empty catalog",
    );
    warn.mockRestore();

    // Empty/degraded results are TTL-cached like successes; advance past TTL.
    vi.advanceTimersByTime(4100);
    fetchMock.mockResolvedValueOnce(okResponse());
    const markets = await fetchMarkets({});
    expect(markets.length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("resolves empty on Markets HTTP 503 without throwing", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    fetchMock.mockResolvedValueOnce({ ok: false, status: 503 } as Response);
    await expect(fetchMarkets({})).resolves.toEqual([]);
    expect(warn).toHaveBeenCalledWith(
      "Markets HTTP 503 — using empty catalog",
    );
    warn.mockRestore();
  });
});
