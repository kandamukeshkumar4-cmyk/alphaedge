import { describe, expect, it } from "vitest";
import { buildBacktestSummaryView, type BacktestSummary } from "./backtest-summary-api";

const BASE: BacktestSummary = {
  n: 2,
  thin_data: true,
  thin_data_threshold: 30,
  brier_score: 0.09,
  market_brier_score: 0.25,
  roi: 1.0,
  n_bets: 2,
  total_pnl: 1.0,
  total_staked: 1.0,
  walk_forward: [
    { seq: 1, scored_at: "2026-07-10T16:00:00Z", brier: 0.09, cumulative_brier: 0.09, cumulative_roi: 1.0 },
    { seq: 2, scored_at: "2026-07-10T17:00:00Z", brier: 0.09, cumulative_brier: 0.09, cumulative_roi: 1.0 },
  ],
  source: "forecast_scores",
  last_updated: "2026-07-10T17:00:00Z",
  paper_trading_only: true,
  signal_only: true,
  disclaimer: "Walk-forward research metrics from REAL resolutions only.",
};

describe("buildBacktestSummaryView", () => {
  it("is honestly empty and unreachable on a null response", () => {
    const view = buildBacktestSummaryView(null);
    expect(view.reachable).toBe(false);
    expect(view.available).toBe(false);
    expect(view.brierSeries).toHaveLength(0);
    expect(view.disclaimer.length).toBeGreaterThan(0);
  });

  it("is honestly empty at n=0 (reachable, no fabricated curve)", () => {
    const view = buildBacktestSummaryView({
      ...BASE,
      n: 0,
      brier_score: null,
      market_brier_score: null,
      roi: null,
      n_bets: 0,
      walk_forward: [],
      source: "none",
      last_updated: null,
    });
    expect(view.reachable).toBe(true);
    expect(view.available).toBe(false);
    expect(view.hasBrierSeries).toBe(false);
    expect(view.hasRoiSeries).toBe(false);
  });

  it("carries the thin_data provisional caveat", () => {
    const view = buildBacktestSummaryView(BASE);
    expect(view.caveat).toContain("Only 2 resolved forecasts");
    expect(view.caveat).toContain("30");
  });

  it("drops the caveat when the sample is big enough", () => {
    expect(buildBacktestSummaryView({ ...BASE, n: 45, thin_data: false }).caveat).toBeNull();
  });

  it("builds model-vs-market Brier tiles with a verdict", () => {
    const view = buildBacktestSummaryView(BASE);
    expect(view.brierLabel).toBe("0.0900");
    expect(view.marketBrierLabel).toBe("0.2500");
    expect(view.brierVerdict).toBe("baseline beats market");
  });

  it("is honest when the market Brier is unavailable (no implied prices)", () => {
    const view = buildBacktestSummaryView({ ...BASE, market_brier_score: null });
    expect(view.marketBrierLabel).toBe("—");
    expect(view.brierVerdict).toBeNull();
  });

  it("formats ROI with tone and n_bets", () => {
    const view = buildBacktestSummaryView(BASE);
    expect(view.roiLabel).toBe("+100.0%");
    expect(view.roiTone).toBe("up");
    expect(view.betsLabel).toBe("2");
    expect(view.pnlLabel).toBe("+$1.00");
  });

  it("says 'no bets placed' instead of faking a 0% ROI", () => {
    const view = buildBacktestSummaryView({ ...BASE, roi: null, n_bets: 0, total_pnl: 0 });
    expect(view.roiLabel).toBe("no bets placed");
    expect(view.roiTone).toBe("neutral");
  });

  it("skips pre-first-bet points in the ROI series (cumulative_roi null)", () => {
    const view = buildBacktestSummaryView({
      ...BASE,
      walk_forward: [
        { seq: 1, scored_at: "2026-07-10T15:00:00Z", brier: 0.2, cumulative_brier: 0.2, cumulative_roi: null },
        { seq: 2, scored_at: "2026-07-10T16:00:00Z", brier: 0.09, cumulative_brier: 0.145, cumulative_roi: 0.5 },
        { seq: 3, scored_at: "2026-07-10T17:00:00Z", brier: 0.09, cumulative_brier: 0.127, cumulative_roi: 1.0 },
      ],
    });
    expect(view.brierSeries).toHaveLength(3);
    expect(view.roiSeries).toHaveLength(2);
    expect(view.roiSeries[0]).toEqual({ seq: 2, value: 0.5 });
  });

  it("needs at least 2 points to draw a line", () => {
    const view = buildBacktestSummaryView({
      ...BASE,
      n: 1,
      walk_forward: [BASE.walk_forward[0]],
    });
    expect(view.hasBrierSeries).toBe(false);
    expect(view.hasRoiSeries).toBe(false);
  });
});
