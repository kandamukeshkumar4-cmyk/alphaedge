import { describe, expect, it } from "vitest";
import {
  buildCategorySummaryView,
  type CategorySummaryResponse,
} from "./category-summary-api";
import type { OpportunityRow } from "./opportunities-api";

function opp(overrides: Partial<OpportunityRow>): OpportunityRow {
  return {
    slug: "nba-cat-lal-bos",
    title: "Lakers vs Celtics",
    model_p: 0.8,
    market_p: 0.5,
    edge: 0.3,
    direction: "YES",
    yes_price: 0.5,
    liquidity: 5000,
    top_signal: null,
    ...overrides,
  };
}

function response(overrides: Partial<CategorySummaryResponse>): CategorySummaryResponse {
  return {
    category: "NBA",
    found: true,
    market_count: 1,
    mean_abs_edge: 0.3,
    top_opportunities: [opp({})],
    recent_signal_count: 1,
    resolved_n: 1,
    resolved_accuracy: 1.0,
    paper_trading_only: true,
    signal_only: true,
    disclaimer: "Category intelligence — NOT an order feed.",
    generated_at: "2026-07-10T18:00:00Z",
    cached: false,
    ...overrides,
  };
}

describe("buildCategorySummaryView", () => {
  it("marks the view unreachable for a null response and echoes the requested category", () => {
    const view = buildCategorySummaryView(null, "sports");
    expect(view.reachable).toBe(false);
    expect(view.found).toBe(false);
    expect(view.category).toBe("sports");
    expect(view.marketCount).toBe(0);
    expect(view.meanEdgeLabel).toBe("—");
    expect(view.resolvedAccuracyLabel).toBe("—");
    expect(view.topOpportunities).toEqual([]);
  });

  it("renders an honest found:false aggregate for an unknown category", () => {
    const view = buildCategorySummaryView(
      response({
        category: "does-not-exist",
        found: false,
        market_count: 0,
        mean_abs_edge: null,
        top_opportunities: [],
        recent_signal_count: 0,
        resolved_n: 0,
        resolved_accuracy: null,
      }),
    );
    expect(view.reachable).toBe(true);
    expect(view.found).toBe(false);
    expect(view.marketCount).toBe(0);
    expect(view.meanEdgeLabel).toBe("—");
    expect(view.resolvedAccuracyLabel).toBe("—");
    expect(view.topOpportunities).toEqual([]);
  });

  it("formats a known-category aggregate with edge, signals and resolved accuracy", () => {
    const view = buildCategorySummaryView(response({}));
    expect(view.found).toBe(true);
    expect(view.category).toBe("NBA");
    expect(view.marketCount).toBe(1);
    expect(view.meanEdgeLabel).toBe("30.0 pts");
    expect(view.recentSignalCount).toBe(1);
    expect(view.resolvedN).toBe(1);
    expect(view.resolvedAccuracyLabel).toBe("100%");
  });

  it("reuses the R01 row builder for top opportunities", () => {
    const view = buildCategorySummaryView(
      response({
        top_opportunities: [
          opp({ slug: "y", edge: 0.3, direction: "YES", model_p: 0.8, market_p: 0.5 }),
        ],
      }),
    );
    const r = view.topOpportunities[0];
    expect(r.slug).toBe("y");
    expect(r.edgeLabel).toBe("30.0 pts");
    expect(r.modelLabel).toBe("80%");
    expect(r.directionTone).toBe("up");
    expect(r.href).toContain("y");
  });

  it("treats a null mean_abs_edge and null resolved_accuracy as honest placeholders", () => {
    const view = buildCategorySummaryView(
      response({ mean_abs_edge: null, resolved_accuracy: null, resolved_n: 0 }),
    );
    expect(view.meanAbsEdge).toBeNull();
    expect(view.meanEdgeLabel).toBe("—");
    expect(view.resolvedAccuracy).toBeNull();
    expect(view.resolvedAccuracyLabel).toBe("—");
  });

  it("coerces non-finite / missing counts to zero without throwing", () => {
    const view = buildCategorySummaryView(
      response({
        market_count: Number.NaN as unknown as number,
        recent_signal_count: Number.NaN as unknown as number,
        resolved_n: Number.NaN as unknown as number,
      }),
    );
    expect(view.marketCount).toBe(0);
    expect(view.recentSignalCount).toBe(0);
    expect(view.resolvedN).toBe(0);
  });

  it("passes through the cached flag and backend disclaimer", () => {
    const view = buildCategorySummaryView(response({ cached: true }));
    expect(view.cached).toBe(true);
    expect(view.disclaimer).toContain("NOT an order feed");
  });
});
