import { describe, expect, it } from "vitest";
import {
  buildBacktestRunView,
  type BacktestRunResponse,
} from "./backtest-run-api";

const RAN: BacktestRunResponse = {
  ran: true,
  slug: "mkt-good",
  reason: null,
  n: 3,
  thin_data: true,
  thin_data_threshold: 30,
  brier_score: 0.0467,
  market_brier_score: 0.22,
  roi: 0.875,
  n_bets: 3,
  total_pnl: 1.4,
  total_staked: 1.6,
  walk_forward: [
    { seq: 1, scored_at: "2026-07-10T15:00:00Z", brier: 0.09, cumulative_brier: 0.09, cumulative_roi: null },
    { seq: 2, scored_at: "2026-07-10T16:00:00Z", brier: 0.02, cumulative_brier: 0.055, cumulative_roi: 0.5 },
    { seq: 3, scored_at: "2026-07-10T17:00:00Z", brier: 0.03, cumulative_brier: 0.0467, cumulative_roi: 0.875 },
  ],
  source: "forecast_scores",
  last_updated: "2026-07-10T17:00:00Z",
  paper_trading_only: true,
  signal_only: true,
  disclaimer: "Self-serve walk-forward research metrics — paper only.",
};

describe("buildBacktestRunView", () => {
  it("is unreachable on a null response (no reason message)", () => {
    const view = buildBacktestRunView(null);
    expect(view.reachable).toBe(false);
    expect(view.status).toBe("unreachable");
    expect(view.ran).toBe(false);
    expect(view.notRanMessage).toBeNull();
    expect(view.disclaimer.length).toBeGreaterThan(0);
  });

  it("surfaces the unknown_slug reason honestly (reachable, not ran)", () => {
    const view = buildBacktestRunView({
      ...RAN,
      ran: false,
      slug: "does-not-exist",
      reason: "unknown_slug",
      n: 0,
      brier_score: null,
      market_brier_score: null,
      roi: null,
      n_bets: 0,
      total_pnl: 0,
      total_staked: 0,
      walk_forward: [],
      source: "none",
      last_updated: null,
    });
    expect(view.reachable).toBe(true);
    expect(view.status).toBe("not-ran");
    expect(view.ran).toBe(false);
    expect(view.notRanMessage).toContain("No resolved forecast history");
    expect(view.hasBrierSeries).toBe(false);
    expect(view.brierSeries).toHaveLength(0);
  });

  it("surfaces too_few_resolves with a distinct message", () => {
    const view = buildBacktestRunView({
      ...RAN,
      ran: false,
      reason: "too_few_resolves",
      n: 0,
      walk_forward: [],
    });
    expect(view.notRanMessage).toContain("at least 3");
  });

  it("falls back to a generic message on an unknown reason string", () => {
    const view = buildBacktestRunView({ ...RAN, ran: false, reason: "weird", n: 0, walk_forward: [] });
    expect(view.notRanMessage).toBe("This market cannot be backtested right now.");
  });

  it("builds tiles + a brier verdict when ran", () => {
    const view = buildBacktestRunView(RAN);
    expect(view.ran).toBe(true);
    expect(view.status).toBe("ran");
    expect(view.slug).toBe("mkt-good");
    expect(view.brierLabel).toBe("0.0467");
    expect(view.marketBrierLabel).toBe("0.2200");
    expect(view.brierVerdict).toBe("model beats market");
    expect(view.roiLabel).toBe("+87.5%");
    expect(view.roiTone).toBe("up");
    expect(view.betsLabel).toBe("3");
    expect(view.pnlLabel).toBe("+$1.40");
  });

  it("carries the thin_data provisional caveat while ran", () => {
    const view = buildBacktestRunView(RAN);
    expect(view.caveat).toContain("Only 3 resolved forecasts");
    expect(view.caveat).toContain("30");
  });

  it("drops the caveat when the sample is big enough", () => {
    expect(
      buildBacktestRunView({ ...RAN, n: 40, thin_data: false }).caveat,
    ).toBeNull();
  });

  it("skips pre-first-bet points in the ROI series (cumulative_roi null)", () => {
    const view = buildBacktestRunView(RAN);
    expect(view.brierSeries).toHaveLength(3);
    expect(view.roiSeries).toHaveLength(2);
    expect(view.roiSeries[0]).toEqual({ seq: 2, value: 0.5 });
    expect(view.hasBrierSeries).toBe(true);
    expect(view.hasRoiSeries).toBe(true);
  });

  it("says 'no bets placed' instead of faking a 0% ROI", () => {
    const view = buildBacktestRunView({ ...RAN, roi: null, n_bets: 0, total_pnl: 0 });
    expect(view.roiLabel).toBe("no bets placed");
    expect(view.roiTone).toBe("neutral");
  });
});
