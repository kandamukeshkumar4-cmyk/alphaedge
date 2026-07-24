import { describe, expect, it, vi } from "vitest";

import {
  fetchPortfolioAnalytics,
  getMockPortfolioAnalytics,
  isEmptyPortfolioAnalytics,
  normalizeAnalyticsDays,
  normalizePortfolioAnalytics,
} from "./portfolio-analytics-api";

describe("portfolio-analytics-api", () => {
  it("fetchPortfolioAnalytics hits GET /api/v1/portfolio/analytics?days= with bearer and returns live data", async () => {
    const liveBody = {
      pnl_series: [
        {
          date: "2026-07-24",
          realized_pnl: 6,
          unrealized_pnl: 0,
          equity: 100_006,
        },
      ],
      summary: {
        total_realized: 6,
        total_unrealized: 0,
        win_rate: 1,
        trades_closed: 1,
        trades_open: 0,
        best_trade: 6,
        worst_trade: 6,
        avg_hold_hours: 2.5,
      },
      calibration: {
        buckets: [
          { predicted_prob_bucket: "0.4-0.5", actual_rate: 1, n: 1 },
        ],
        paper_trading_only: true,
      },
    };
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => liveBody,
    } as Response);

    const result = await fetchPortfolioAnalytics({
      days: 30,
      token: "jwt",
      apiBase: "http://api.test",
      fetcher,
    });

    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/portfolio/analytics?days=30",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer jwt" }),
      }),
    );
    expect(result.source).toBe("live");
    expect(result.data.summary.total_realized).toBe(6);
    expect(result.data.calibration.buckets).toEqual([
      { predicted_prob_bucket: "0.4-0.5", actual_rate: 1, n: 1 },
    ]);
    expect(result.data.calibration.paper_trading_only).toBe(true);
  });

  it("falls back to the seeded PAPER mock when the live API fails", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("backend down"));

    const result = await fetchPortfolioAnalytics({
      days: 7,
      token: null,
      apiBase: "http://api.test",
      fetcher,
    });

    expect(result.source).toBe("mock");
    expect(result.data.pnl_series).toHaveLength(7);
    expect(result.data.summary.trades_closed).toBeGreaterThan(0);
    expect(result.data.calibration.paper_trading_only).toBe(true);
    expect(result.data).toEqual(getMockPortfolioAnalytics(7));
  });

  it("normalizes days, tolerates drift, and detects empty portfolios", () => {
    expect(normalizeAnalyticsDays(7)).toBe(7);
    expect(normalizeAnalyticsDays(90)).toBe(90);
    expect(normalizeAnalyticsDays(12)).toBe(30);
    expect(normalizeAnalyticsDays("nope")).toBe(30);

    const normalized = normalizePortfolioAnalytics({
      pnl_series: [{ date: "2026-07-01", realized_pnl: "x", equity: 1 }],
      summary: { total_realized: 4.2, trades_closed: 2.8 },
      calibration: {
        buckets: [{ predicted_prob_bucket: "0.5-0.6", actual_rate: 0.5, n: 2 }],
        paper_trading_only: true,
      },
    });
    expect(normalized.pnl_series[0]).toEqual({
      date: "2026-07-01",
      realized_pnl: 0,
      unrealized_pnl: 0,
      equity: 1,
    });
    expect(normalized.summary.trades_closed).toBe(3);
    expect(normalized.summary.total_realized).toBe(4.2);
    expect(isEmptyPortfolioAnalytics(normalized)).toBe(false);
    expect(
      isEmptyPortfolioAnalytics(
        normalizePortfolioAnalytics({
          pnl_series: [],
          summary: {},
          calibration: { buckets: [], paper_trading_only: true },
        }),
      ),
    ).toBe(true);
  });
});
