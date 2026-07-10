import { describe, expect, it } from "vitest";

import {
  buildSignalsDashboardView,
  categorizeSignal,
  formatMarketLabel,
  formatSignalTypeLabel,
} from "./signals-dashboard-view-model";

describe("categorizeSignal", () => {
  it("maps the specialised backend signal types to filter families", () => {
    expect(categorizeSignal("screener:momentum")).toBe("screener");
    expect(categorizeSignal("screener:expiry_fade")).toBe("screener");
    expect(categorizeSignal("delta:weather_edge")).toBe("weather");
    expect(categorizeSignal("dutching")).toBe("dutching");
    expect(categorizeSignal("delta:news_arrival")).toBe("news");
    expect(categorizeSignal("news:mispricing")).toBe("news");
    expect(categorizeSignal("anomaly:unusual_flow")).toBe("anomaly");
    expect(categorizeSignal("delta:price_jump")).toBe("anomaly");
  });

  it("routes anything else to 'other'", () => {
    expect(categorizeSignal("alignment")).toBe("other");
    expect(categorizeSignal("whale_delta")).toBe("other");
    expect(categorizeSignal("arbitrage")).toBe("other");
    expect(categorizeSignal("forecast")).toBe("other");
  });
});

describe("formatMarketLabel", () => {
  it("keeps human titles as-is", () => {
    expect(formatMarketLabel("Will Bitcoin reach $65k?")).toBe("Will Bitcoin reach $65k?");
  });

  it("humanizes slug-like market names", () => {
    expect(formatMarketLabel("pm-will-bitcoin-reach-65k-in-july-2026")).toBe(
      "Will bitcoin reach 65k in july 2026",
    );
    expect(
      formatMarketLabel(
        "pm-will-ayo-dosunmu-play-for-the-oklahoma-city-thunder-in-2026-27-abc12345",
      ),
    ).toBe("Will ayo dosunmu play for the oklahoma city thunder in 2026 27");
  });
});

describe("formatSignalTypeLabel", () => {
  it("turns jargon types into plain labels", () => {
    expect(formatSignalTypeLabel("delta:price_jump")).toBe("Price jump");
    expect(formatSignalTypeLabel("smart_money")).toBe("Smart money");
    expect(formatSignalTypeLabel("forecast")).toBe("Forecast");
  });
});

describe("signals dashboard view model", () => {
  it("humanizes blocked/provisional copy and empty metrics", () => {
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
          signal_type: "delta:price_jump",
          platform: "polymarket",
          market_id: "m1",
          market_name: "pm-will-bitcoin-reach-65k-in-july-2026",
          implied_edge: null,
          sample_size: 0,
          is_edge: false,
          provisional: true,
          created_at: "2026-01-01T00:00:00Z",
          resolved: false,
        },
        {
          id: "2",
          signal_type: "forecast",
          platform: "polymarket",
          market_id: "m2",
          market_name: "Market Two",
          implied_edge: 0.03,
          sample_size: 40,
          is_edge: false,
          provisional: false,
          created_at: "2026-01-02T00:00:00Z",
          resolved: false,
        },
      ],
      clv_records: [
        {
          market_slug: "ks-fed-rate-cut-july-2026",
          model_prob: 0.55,
          closing_prob: 0.5,
          clv: 0.05,
          resolved_at: "2026-01-03T00:00:00Z",
          is_edge: true,
        },
      ],
    });

    const provisionalCard = view.signalCards[0];
    expect(provisionalCard.marketName).toBe("Will bitcoin reach 65k in july 2026");
    expect(provisionalCard.signalTypeLabel).toBe("Price jump");
    expect(provisionalCard.statusLabel).toBe("Needs more history");
    expect(provisionalCard.impliedEdgeLabel).toBe("—");
    expect(provisionalCard.sampleSizeLabel).toBe("—");
    expect(provisionalCard.provisionalNote).toContain("under 30");
    expect(provisionalCard.blockedLabel).toBeNull();

    const blockedCard = view.signalCards[1];
    expect(blockedCard.statusLabel).toBe("No edge yet");
    expect(blockedCard.blockedLabel).toContain("honesty check");
    expect(blockedCard.sampleSizeLabel).toBe("40");

    expect(view.clvRows[0].market).toBe("Fed rate cut july 2026");
    expect(view.paperPnlLabel).toBe("$12.50");
  });
});
