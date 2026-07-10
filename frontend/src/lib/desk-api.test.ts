import { describe, expect, it } from "vitest";
import { buildDeskView, type DeskResponse } from "./desk-api";

const BASE: DeskResponse = {
  slug: "pm-will-lakers-beat-celtics",
  market_found: true,
  paper_trading_only: true,
  signal_only: true,
  disclaimer: "Research desk aggregate — signal only; paper trading only.",
  market: { slug: "pm-will-lakers-beat-celtics", title: "Will the Lakers beat the Celtics?", status: "open" },
  edge: {
    predicted_prob: 0.62,
    confidence: 0.7,
    edge_vs_book: 0.12,
    input_feature_hash: "feat-abc",
    predicted_at: "2026-07-10T17:55:00+00:00",
    source: "prediction_log",
  },
  smart_money: {
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
    generated_at: "2026-07-10T18:00:00+00:00",
  },
  arb: {
    pm_slug: "pm-will-lakers-beat-celtics",
    ks_slug: "ks-kxnba-lalbos-26jan15",
    pm_title: "Lakers beat Celtics",
    ks_title: "LAL def BOS",
    confidence: 0.9,
    reasons: ["title", "date"],
    stale: false,
    matched_at: "2026-07-10T18:00:00+00:00",
    updated_at: "2026-07-10T18:00:00+00:00",
  },
  signals: [
    {
      id: "sig-1",
      signal_type: "news:mispricing",
      platform: "polymarket",
      market_id: "pm-will-lakers-beat-celtics",
      headline_eligible: true,
      payload: {
        headline: "Star center ruled out",
        news_url: "https://example.com/news",
        model_p: 0.62,
        market_p: 0.5,
        gap: 0.12,
      },
      created_at: "2026-07-10T18:00:00+00:00",
    },
    {
      id: "sig-2",
      signal_type: "anomaly:unusual_flow",
      platform: "polymarket",
      market_id: "pm-will-lakers-beat-celtics",
      headline_eligible: true,
      payload: { catalyst: "none_found", kind: "price_jump" },
      created_at: "2026-07-10T17:00:00+00:00",
    },
  ],
  generated_at: "2026-07-10T18:00:00+00:00",
};

describe("buildDeskView", () => {
  it("returns honest empty for a null response", () => {
    const view = buildDeskView(null);
    expect(view.found).toBe(false);
    expect(view.edge).toBeNull();
    expect(view.arb).toBeNull();
    expect(view.signals).toHaveLength(0);
    expect(view.smartMoney.found).toBe(false);
    expect(view.disclaimer.length).toBeGreaterThan(0);
  });

  it("returns honest empty when market_found is false (unknown slug → 200)", () => {
    const view = buildDeskView({
      ...BASE,
      market_found: false,
      market: null,
      edge: null,
      arb: null,
      signals: [],
      smart_money: { ...BASE.smart_money!, market_found: false },
    });
    expect(view.found).toBe(false);
    expect(view.edge).toBeNull();
    expect(view.smartMoney.found).toBe(false);
    expect(view.hasSignals).toBe(false);
  });

  it("formats the model-vs-market edge chip", () => {
    const view = buildDeskView(BASE);
    expect(view.edge).not.toBeNull();
    expect(view.edge!.modelLabel).toBe("62%");
    expect(view.edge!.edgeLabel).toBe("+12.0 pts");
    expect(view.edge!.edgeTone).toBe("up");
    expect(view.edge!.confidenceLabel).toBe("conf 0.70");
  });

  it("keeps the edge honest when the book is empty (edge_vs_book null)", () => {
    const view = buildDeskView({
      ...BASE,
      edge: { ...BASE.edge!, edge_vs_book: null },
    });
    expect(view.edge!.edgeLabel).toBeNull();
    expect(view.edge!.edgeTone).toBe("neutral");
  });

  it("renders no edge section when no prediction exists", () => {
    expect(buildDeskView({ ...BASE, edge: null }).edge).toBeNull();
  });

  it("summarises smart money: concentration + last large flow", () => {
    const view = buildDeskView(BASE);
    expect(view.smartMoney.found).toBe(true);
    expect(view.smartMoney.concentrationLabel).toBe("90.9%");
    expect(view.smartMoney.lastFlow).toMatchObject({
      wallet: "0xwhaleA…",
      direction: "buy",
      outcome: "YES",
      isBuy: true,
    });
  });

  it("surfaces per-section smart-money errors instead of hiding them", () => {
    const view = buildDeskView({
      ...BASE,
      smart_money: {
        ...BASE.smart_money!,
        top_holders: { ...BASE.smart_money!.top_holders, error: "holders unavailable" },
        recent_large_flows: { whale_count: 0, deltas: [], error: null },
      },
    });
    expect(view.smartMoney.errors).toContain("holders unavailable");
    expect(view.smartMoney.lastFlow).toBeNull();
  });

  it("builds the arb chip with counterpart + confidence + match reasons", () => {
    const view = buildDeskView(BASE);
    expect(view.arb).toMatchObject({
      counterpartSlug: "ks-kxnba-lalbos-26jan15",
      counterpartTitle: "LAL def BOS",
      confidenceLabel: "90%",
      stale: false,
    });
    // spread_bps is not in the documented H01 arb shape → degrade to reasons.
    expect(view.arb!.spreadNote).toBe("matched on title, date");
  });

  it("uses spread_bps when a future contract adds it", () => {
    const view = buildDeskView({
      ...BASE,
      arb: { ...BASE.arb!, spread_bps: 42 } as DeskResponse["arb"],
    });
    expect(view.arb!.spreadNote).toBe("42 bps");
  });

  it("omits the arb chip when no venue match exists", () => {
    expect(buildDeskView({ ...BASE, arb: null }).arb).toBeNull();
  });

  it("extracts signal evidence per row and keeps evidence-less rows", () => {
    const view = buildDeskView(BASE);
    expect(view.hasSignals).toBe(true);
    expect(view.signals).toHaveLength(2);
    expect(view.signals[0].typeLabel).toBe("news mispricing");
    expect(view.signals[0].evidence).toMatchObject({ kind: "news", headline: "Star center ruled out" });
    expect(view.signals[1].evidence).toMatchObject({ kind: "catalyst" });
  });

  it("is honest with zero signals", () => {
    const view = buildDeskView({ ...BASE, signals: [] });
    expect(view.hasSignals).toBe(false);
    expect(view.signals).toHaveLength(0);
  });
});
