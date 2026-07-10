import { describe, expect, it } from "vitest";
import { buildSmartMoneyView, type SmartMoney } from "./smart-money-api";

const BASE: SmartMoney = {
  slug: "pm-will-lakers-beat-celtics",
  hours: 24,
  market_found: true,
  paper_trading_only: true,
  signal_only: true,
  disclaimer: "Research signal only.",
  top_holders: { wallet_count: 3, top_n: 5, top_share: 0.9091, total_size: 1650, error: null },
  recent_large_flows: {
    whale_count: 1,
    deltas: [
      { wallet: "0xwhaleA…", action: "add", outcome: "YES", direction: "buy", size_change: 500 },
      { wallet: "0xwhaleB…", action: "trim", outcome: "NO", direction: "sell", size_change: 300 },
    ],
    error: null,
  },
  depth_skew: { bid_size: 12, ask_size: 4, skew: 0.5, levels: 3, error: null },
  trade_intensity: { fill_count: 40, notional: 12000, fills_per_hour: 10, error: null },
  generated_at: "2026-07-09T18:00:00+00:00",
};

describe("buildSmartMoneyView", () => {
  it("returns honest empty when market_found is false", () => {
    const view = buildSmartMoneyView({ ...BASE, market_found: false });
    expect(view.found).toBe(false);
    expect(view.flows).toHaveLength(0);
    expect(view.disclaimer).toContain("Research signal only");
  });

  it("returns honest empty for a null response", () => {
    expect(buildSmartMoneyView(null).found).toBe(false);
  });

  it("formats concentration, wallet count, and total size", () => {
    const view = buildSmartMoneyView(BASE);
    expect(view.found).toBe(true);
    expect(view.concentrationLabel).toBe("90.9%");
    expect(view.walletCountLabel).toBe("3");
    expect(view.totalSizeLabel).toBe("1.6K");
    expect(view.concentrationRatio).toBeCloseTo(0.9091, 4);
  });

  it("tones the depth skew by sign", () => {
    expect(buildSmartMoneyView(BASE).depthSkewTone).toBe("up");
    expect(buildSmartMoneyView({ ...BASE, depth_skew: { ...BASE.depth_skew, skew: -0.5 } }).depthSkewTone).toBe("down");
    expect(buildSmartMoneyView({ ...BASE, depth_skew: { ...BASE.depth_skew, skew: 0 } }).depthSkewTone).toBe("neutral");
  });

  it("maps whale flows with buy/sell direction", () => {
    const view = buildSmartMoneyView(BASE);
    expect(view.hasFlows).toBe(true);
    expect(view.flows[0]).toMatchObject({ wallet: "0xwhaleA…", isBuy: true, sizeLabel: "500" });
    expect(view.flows[1].isBuy).toBe(false);
  });

  it("collects per-section errors", () => {
    const view = buildSmartMoneyView({
      ...BASE,
      trade_intensity: { ...BASE.trade_intensity, error: "no fills" },
    });
    expect(view.errors).toContain("no fills");
  });

  it("caps the intensity ratio at 1", () => {
    const view = buildSmartMoneyView({
      ...BASE,
      trade_intensity: { ...BASE.trade_intensity, fills_per_hour: 999 },
    });
    expect(view.intensityRatio).toBe(1);
  });
});
