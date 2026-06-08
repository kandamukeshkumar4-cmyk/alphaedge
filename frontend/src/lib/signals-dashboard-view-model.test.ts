import { describe, expect, it } from "vitest";

import { buildSignalsDashboardView } from "./signals-dashboard-view-model";

describe("signals dashboard view model", () => {
  it("marks blocked signals and provisional sample sizes", () => {
    const view = buildSignalsDashboardView({
      paper_trading_only: true,
      disclaimer: "Research only",
      llm_explanation: null,
      paper_pnl: {
        total_pnl: 12.5,
        n_bets: 2,
        win_rate: 0.5,
        note: "paper-only",
        disclaimer: "Research only",
        paper_trading_only: true,
      },
      signals: [
        {
          id: "1",
          signal_type: "forecast",
          platform: "polymarket",
          market_id: "m1",
          market_name: "Market One",
          implied_edge: 0.03,
          sample_size: 12,
          is_edge: false,
          provisional: true,
          created_at: "2026-01-01T00:00:00Z",
          resolved: false,
        },
      ],
      clv_records: [],
    });

    expect(view.signalCards[0].blockedLabel).toContain("CLV gate blocked");
    expect(view.signalCards[0].provisional).toBe(true);
    expect(view.paperPnlLabel).toBe("$12.50");
  });
});
