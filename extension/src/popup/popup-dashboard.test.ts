import { describe, expect, it } from "vitest";

import { buildPopupDashboardView } from "./popup-dashboard";
import type { ForecastDashboardSummary, ForecastLifecycleSummary } from "../backend-client";

describe("popup mini-dashboard view", () => {
  it("renders metrics, pending queue copy, and the last five resolved results", () => {
    const view = buildPopupDashboardView({
      dashboard: dashboard(),
      lifecycle: lifecycle(6),
      queue: [
        { id: "a", idempotencyKey: "a", status: "pending", message: {} as never, lockedAt: "", updatedAt: "", attempts: 0 },
        { id: "b", idempotencyKey: "b", status: "failed", message: {} as never, lockedAt: "", updatedAt: "", attempts: 1 },
        { id: "c", idempotencyKey: "c", status: "synced", message: {} as never, lockedAt: "", updatedAt: "", attempts: 1 },
      ],
    });

    expect(view.rollingBrier).toBe("0.210");
    expect(view.independentCount).toBe("12");
    expect(view.anchoredCount).toBe("3");
    expect(view.pendingText).toBe("2 forecasts pending");
    expect(view.lastResolved).toHaveLength(5);
    expect(view.lastResolved[0]).toEqual({
      title: "Resolved market 0",
      score: "Brier 0.040",
      pnl: "Paper P&L 0.32",
    });
  });

  it("shows an empty state when no profile data has loaded", () => {
    const view = buildPopupDashboardView({
      dashboard: null,
      lifecycle: null,
      queue: [],
    });

    expect(view.empty).toBe(true);
    expect(view.rollingBrier).toBe("No resolved forecasts");
    expect(view.pendingText).toBe("0 forecasts pending");
  });
});

function dashboard(): ForecastDashboardSummary {
  return {
    paper_trading_only: true,
    live: {
      resolved_count: 20,
      unresolved_count: 4,
      independent_count: 12,
      anchored_count: 3,
      mean_user_brier: 0.21,
      mean_brier_delta: 0.03,
      synthetic_pnl_total: 2.4,
    },
  };
}

function lifecycle(count: number): ForecastLifecycleSummary {
  return {
    unresolved_count: 0,
    recently_resolved_count: count,
    unresolved: [],
    recently_resolved: Array.from({ length: count }, (_, index) => ({
      forecast_id: `forecast-${index}`,
      external_market_id: `market-${index}`,
      platform: "polymarket",
      title: `Resolved market ${index}`,
      url: "https://polymarket.com/event/resolved",
      outcome_label: "YES",
      user_probability: 0.8,
      market_implied_probability: 0.6,
      locked_at: "2026-06-04T15:00:00.000Z",
      status: "resolved",
      user_brier: 0.04 + index / 100,
      brier_delta: 0.1,
      synthetic_pnl: 0.32,
      resolved_at: "2026-06-05T15:00:00.000Z",
    })),
  };
}
