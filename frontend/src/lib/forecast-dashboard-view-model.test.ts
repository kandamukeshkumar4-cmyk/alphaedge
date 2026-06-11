import { describe, expect, it } from "vitest";

import {
  buildForecastDashboardView,
  type ForecastDashboardViewInput,
} from "./forecast-dashboard-view-model";

describe("forecast dashboard view model", () => {
  it("shows a research-only empty state before any forecast is scored", () => {
    const view = buildForecastDashboardView(null);

    expect(view.emptyState).toEqual({
      title: "No locked forecasts yet",
      body: "Lock research-only paper forecasts from the extension or web dashboard to start measuring skill.",
    });
    expect(view.summaryCards.map((card) => card.value)).toEqual(["0", "0", "N/A", "$0.00"]);
  });

  it("labels Brier, calibration, and small category samples as provisional", () => {
    const view = buildForecastDashboardView(sampleDashboard);

    expect(view.qualityLabels).toEqual([
      "Brier provisional: 12/30 resolved",
      "Calibration provisional: 12/150 resolved",
      "Sports category provisional: 12/20 resolved",
    ]);
  });

  it("keeps time, platform, and Brier trend sections in dashboard order", () => {
    const view = buildForecastDashboardView(sampleDashboard);

    expect(view.timeBreakdown.map((row) => `${row.bucket}:${row.count}`)).toEqual([
      "7d+:5",
      "1-7d:3",
      "6-24h:2",
      "1-6h:1",
      "<1h:1",
      "unknown:0",
    ]);
    expect(view.platformBreakdown.map((row) => `${row.platform}:${row.count}`)).toEqual([
      "polymarket:8",
      "kalshi:3",
      "manual:1",
    ]);
    expect(view.brierTrend.map((point) => point.seq)).toEqual([1, 2]);
  });

  it("defaults enriched dashboard sections when the deployed backend has not returned them yet", () => {
    const legacyDashboard = {
      ...sampleDashboard,
      live: {
        resolved_count: 0,
        unresolved_count: 0,
        independent_count: 0,
        anchored_count: 0,
        mean_user_brier: null,
        mean_market_brier: null,
        mean_brier_delta: null,
        synthetic_pnl_total: 0,
        brier_provisional: true,
        calibration_provisional: true,
      },
      category_breakdown: [
        {
          category: "Sports",
          count: 0,
          mean_brier_delta: null,
        },
      ],
      platform_breakdown: undefined,
      time_breakdown: undefined,
      brier_trend: undefined,
    } as unknown as ForecastDashboardViewInput;

    const view = buildForecastDashboardView(legacyDashboard);

    expect(view.platformBreakdown).toEqual([]);
    expect(view.timeBreakdown).toEqual([]);
    expect(view.brierTrend).toEqual([]);
    expect(view.qualityLabels).toEqual([
      "Brier provisional: 0/30 resolved",
      "Calibration provisional: 0/150 resolved",
    ]);
  });
  it("provisional label shown when resolved_count < 30", () => {
    const payload = {
      ...sampleDashboard,
      live: {
        ...sampleDashboard.live,
        resolved_count: 5,
        brier_provisional: true,
        first_independent_mean_brier: 0.18,
        time_weighted_brier: 0.20,
      },
    };
    const view = buildForecastDashboardView(payload);

    expect(view.qualityLabels[0]).toMatch(/Brier provisional/);
    expect(view.firstIndependentBrier.provisional).toBe(true);
  });

  it("calibration provisional when independent < 150", () => {
    const payload = {
      ...sampleDashboard,
      live: {
        ...sampleDashboard.live,
        calibration_provisional: true,
      },
    };
    const view = buildForecastDashboardView(payload);

    expect(view.qualityLabels.some((l) => /Calibration provisional/.test(l))).toBe(true);
  });

  it("empty state when no forecasts — time_weighted_brier null renders dash", () => {
    const payload: ForecastDashboardViewInput = {
      ...sampleDashboard,
      live: {
        resolved_count: 0,
        unresolved_count: 0,
        independent_count: 0,
        anchored_count: 0,
        headline_count: 0,
        mean_user_brier: null,
        mean_market_brier: null,
        mean_brier_delta: null,
        synthetic_pnl_total: 0,
        brier_provisional: true,
        calibration_provisional: true,
        first_independent_count: 0,
        first_independent_mean_brier: null,
        time_weighted_brier: null,
      },
      calibration: [],
      brier_trend: [],
    };
    const view = buildForecastDashboardView(payload);

    expect(view.emptyState).not.toBeNull();
    expect(view.summaryCards.map((c) => c.value)).toEqual(["0", "0", "N/A", "$0.00"]);
    expect(view.firstIndependentBrier.value).toBe("—");
    expect(view.timeWeightedBrier.value).toBe("—");
  });
});

const sampleDashboard: ForecastDashboardViewInput = {
  forecaster_id: "11111111-1111-1111-1111-111111111111",
  paper_trading_only: true,
  disclaimer: "Research and paper simulation only.",
  live: {
    resolved_count: 12,
    unresolved_count: 4,
    headline_count: 10,
    independent_count: 10,
    anchored_count: 2,
    mean_user_brier: 0.18,
    mean_market_brier: 0.22,
    mean_brier_delta: 0.04,
    synthetic_pnl_total: 3.5,
    brier_provisional: true,
    calibration_provisional: true,
    first_independent_count: 5,
    first_independent_mean_brier: 0.12,
    time_weighted_brier: 0.14,
  },
  practice: {
    resolved_count: 2,
    mean_user_brier: 0.2,
    mean_brier_delta: 0.01,
  },
  calibration: [],
  category_breakdown: [
    {
      category: "Sports",
      count: 12,
      mean_brier_delta: 0.04,
      provisional: true,
    },
  ],
  platform_breakdown: [
    { platform: "polymarket", count: 8, mean_brier_delta: 0.05 },
    { platform: "kalshi", count: 3, mean_brier_delta: 0.02 },
    { platform: "manual", count: 1, mean_brier_delta: null },
  ],
  time_breakdown: [
    { bucket: "7d+", count: 5, mean_brier_delta: 0.07 },
    { bucket: "1-7d", count: 3, mean_brier_delta: 0.04 },
    { bucket: "6-24h", count: 2, mean_brier_delta: 0.01 },
    { bucket: "1-6h", count: 1, mean_brier_delta: -0.02 },
    { bucket: "<1h", count: 1, mean_brier_delta: null },
    { bucket: "unknown", count: 0, mean_brier_delta: null },
  ],
  brier_trend: [
    { seq: 1, locked_at: "2026-06-01T00:00:00Z", user_brier: 0.2, market_brier: 0.24 },
    { seq: 2, locked_at: "2026-06-02T00:00:00Z", user_brier: 0.16, market_brier: 0.2 },
  ],
};
