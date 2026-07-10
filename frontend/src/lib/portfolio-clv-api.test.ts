import { describe, expect, it } from "vitest";
import {
  buildClvSummaryView,
  type PortfolioClvSummary,
} from "./portfolio-clv-api";

const HISTOGRAM = [
  { label: "<= -0.10", lo: null, hi: -0.1, count: 0 },
  { label: "-0.10..-0.05", lo: -0.1, hi: -0.05, count: 0 },
  { label: "-0.05..0.00", lo: -0.05, hi: 0.0, count: 1 },
  { label: "0.00..0.05", lo: 0.0, hi: 0.05, count: 0 },
  { label: "0.05..0.10", lo: 0.05, hi: 0.1, count: 1 },
  { label: ">= 0.10", lo: 0.1, hi: null, count: 2 },
];

const POPULATED: PortfolioClvSummary = {
  count: 4,
  mean: 0.075,
  positive_share: 0.75,
  total_clv: 0.3,
  histogram: HISTOGRAM,
  matched_slugs: 3,
  settled_orders: 5,
  source: "paper_orders",
  paper_trading_only: true,
  disclaimer: "Realized CLV on settled paper trades only.",
};

describe("buildClvSummaryView", () => {
  it("is unreachable on a null response (anon / 401)", () => {
    const view = buildClvSummaryView(null);
    expect(view.reachable).toBe(false);
    expect(view.available).toBe(false);
    expect(view.emptyMessage).toBeNull();
    expect(view.disclaimer.length).toBeGreaterThan(0);
  });

  it("honest empty when no settled orders (source none)", () => {
    const view = buildClvSummaryView({
      ...POPULATED,
      count: 0,
      mean: null,
      positive_share: null,
      total_clv: 0,
      histogram: HISTOGRAM.map((b) => ({ ...b, count: 0 })),
      matched_slugs: 0,
      settled_orders: 0,
      source: "none",
    });
    expect(view.reachable).toBe(true);
    expect(view.available).toBe(false);
    expect(view.emptyMessage).toContain("No settled paper trades yet");
    expect(view.bars).toHaveLength(0);
  });

  it("honest empty when settled orders exist but none matched a closing line", () => {
    const view = buildClvSummaryView({
      ...POPULATED,
      count: 0,
      mean: null,
      positive_share: null,
      total_clv: 0,
      histogram: HISTOGRAM.map((b) => ({ ...b, count: 0 })),
      matched_slugs: 0,
      settled_orders: 3,
      source: "paper_orders",
    });
    expect(view.available).toBe(false);
    expect(view.emptyMessage).toContain("resolved closing line");
    expect(view.settledOrders).toBe(3);
  });

  it("builds tiles + normalized histogram bars for a real distribution", () => {
    const view = buildClvSummaryView(POPULATED);
    expect(view.available).toBe(true);
    expect(view.countLabel).toBe("4");
    expect(view.meanValue).toBe(0.075);
    expect(view.meanLabel).toBe("+7.5 pts");
    expect(view.meanTone).toBe("up");
    expect(view.positiveShareValue).toBe(0.75);
    expect(view.positiveShareLabel).toBe("75%");
    expect(view.totalClvLabel).toBe("+30.0 pts");
    expect(view.bars).toHaveLength(6);
    // Fullest bin (>= 0.10, count 2) is full height; a count-1 bin is half.
    const top = view.bars.find((b) => b.label === ">= 0.10");
    expect(top?.fraction).toBe(1);
    expect(top?.tone).toBe("up");
    const neg = view.bars.find((b) => b.label === "-0.05..0.00");
    expect(neg?.fraction).toBe(0.5);
    expect(neg?.tone).toBe("down");
  });

  it("renders a negative mean/total with a down tone", () => {
    const view = buildClvSummaryView({ ...POPULATED, mean: -0.04, total_clv: -0.16 });
    expect(view.meanLabel).toBe("-4.0 pts");
    expect(view.meanTone).toBe("down");
    expect(view.totalClvTone).toBe("down");
  });
});
