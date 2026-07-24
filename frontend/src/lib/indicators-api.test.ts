import { afterEach, describe, expect, it } from "vitest";

import {
  fetchMarketIndicators,
  REGIMES,
  resetIndicatorsFetch,
  setIndicatorsFetch,
  sma,
} from "@/lib/indicators-api";

describe("indicators-api client", () => {
  afterEach(() => resetIndicatorsFetch());

  it("normalizes a live indicators payload (tolerant of sparse fields)", async () => {
    setIndicatorsFetch(
      (async () =>
        new Response(
          JSON.stringify({
            slug: "nba-2025-01-15-lal-bos",
            points: [
              { t: 1_750_000_000, close: 0.51 },
              { t: 1_750_003_600, close: 0.53 },
            ],
            // Only RSI supplied — everything else must normalize to null.
            indicators: { rsi_14: 57.3 },
            regime: "trending_up",
            paper_trading_only: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        )) as typeof fetch,
    );

    const { data, source } = await fetchMarketIndicators("nba-2025-01-15-lal-bos");
    expect(source).toBe("live");
    expect(data.slug).toBe("nba-2025-01-15-lal-bos");
    expect(data.regime).toBe("trending_up");
    expect(data.points).toHaveLength(2);
    expect(data.indicators.rsi_14).toBe(57.3);
    expect(data.indicators.macd).toEqual({ macd: null, signal: null, hist: null });
    expect(data.indicators.bollinger).toEqual({ upper: null, mid: null, lower: null });
    expect(data.indicators.sma_20).toBeNull();
    expect(data.indicators.adx_14).toBeNull();
    expect(data.paper_trading_only).toBe(true);
  });

  it("derives a self-consistent paper mock when the live API is down", async () => {
    setIndicatorsFetch((async () => {
      throw new Error("ECONNREFUSED");
    }) as typeof fetch);

    const { data, source } = await fetchMarketIndicators("nba-2025-01-15-lal-bos", {
      window: 90,
    });
    expect(source).toBe("mock");
    expect(data.paper_trading_only).toBe(true);
    expect(data.points.length).toBe(90);
    expect(REGIMES).toContain(data.regime);

    // Mock SMA-20 must equal the mean of the last 20 closes.
    const closes = data.points.map((p) => p.close);
    expect(data.indicators.sma_20).not.toBeNull();
    expect(data.indicators.sma_20).toBeCloseTo(sma(closes, 20) ?? NaN, 12);

    // Every populated indicator is finite; RSI stays in [0, 100].
    if (data.indicators.rsi_14 !== null) {
      expect(data.indicators.rsi_14).toBeGreaterThanOrEqual(0);
      expect(data.indicators.rsi_14).toBeLessThanOrEqual(100);
    }
    if (data.indicators.adx_14 !== null) {
      expect(data.indicators.adx_14).toBeGreaterThanOrEqual(0);
      expect(data.indicators.adx_14).toBeLessThanOrEqual(100);
    }
    // Points are ascending and bounded like outcome prices.
    for (let i = 1; i < data.points.length; i++) {
      expect(data.points[i]!.t).toBeGreaterThan(data.points[i - 1]!.t);
    }
    for (const point of data.points) {
      expect(point.close).toBeGreaterThan(0);
      expect(point.close).toBeLessThan(1);
    }
  });
});
