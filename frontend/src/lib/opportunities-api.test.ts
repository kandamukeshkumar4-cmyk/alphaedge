import { describe, expect, it } from "vitest";
import {
  buildOpportunitiesView,
  type OpportunitiesResponse,
  type OpportunityRow,
} from "./opportunities-api";

function row(overrides: Partial<OpportunityRow>): OpportunityRow {
  return {
    slug: "mkt-a",
    title: "Market A",
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

function response(rows: OpportunityRow[]): OpportunitiesResponse {
  return {
    opportunities: rows,
    count: rows.length,
    limit: 50,
    min_liquidity: 0,
    direction: null,
    paper_trading_only: true,
    signal_only: true,
    disclaimer: "Opportunity scanner — NOT an order feed.",
    generated_at: "2026-07-10T18:00:00Z",
    cached: false,
  };
}

describe("buildOpportunitiesView", () => {
  it("returns an honest empty view for a null response", () => {
    const view = buildOpportunitiesView(null);
    expect(view.rows).toEqual([]);
    expect(view.count).toBe(0);
    expect(view.totalBeforeFilter).toBe(0);
    expect(view.disclaimer).toContain("NOT an order feed");
  });

  it("preserves backend rank order (does not re-sort)", () => {
    const view = buildOpportunitiesView(
      response([
        row({ slug: "big", edge: 0.3 }),
        row({ slug: "small", edge: 0.1 }),
      ]),
    );
    expect(view.rows.map((r) => r.slug)).toEqual(["big", "small"]);
  });

  it("formats the absolute edge as points and picks a direction tone", () => {
    const view = buildOpportunitiesView(
      response([
        row({ slug: "y", edge: 0.3, direction: "YES", model_p: 0.8, market_p: 0.5 }),
        row({ slug: "n", edge: 0.2, direction: "NO", model_p: 0.3, market_p: 0.5 }),
      ]),
    );
    expect(view.rows[0].edgeLabel).toBe("30.0 pts");
    expect(view.rows[0].modelLabel).toBe("80%");
    expect(view.rows[0].marketLabel).toBe("50%");
    expect(view.rows[0].directionTone).toBe("up");
    expect(view.rows[1].directionTone).toBe("down");
  });

  it("takes the absolute value of a signed edge (never negative points)", () => {
    const view = buildOpportunitiesView(response([row({ edge: -0.25 })]));
    expect(view.rows[0].edgeLabel).toBe("25.0 pts");
    expect(view.rows[0].edge).toBeCloseTo(0.25);
  });

  it("filters by direction lean", () => {
    const view = buildOpportunitiesView(
      response([
        row({ slug: "y", direction: "YES" }),
        row({ slug: "n", direction: "NO" }),
      ]),
      { direction: "NO" },
    );
    expect(view.rows.map((r) => r.slug)).toEqual(["n"]);
    expect(view.count).toBe(1);
    expect(view.totalBeforeFilter).toBe(2);
  });

  it("drops rows below the min-liquidity floor", () => {
    const view = buildOpportunitiesView(
      response([
        row({ slug: "thick", liquidity: 9000 }),
        row({ slug: "thin", liquidity: 100 }),
      ]),
      { minLiquidity: 1000 },
    );
    expect(view.rows.map((r) => r.slug)).toEqual(["thick"]);
  });

  it("builds news evidence from a top-signal citation", () => {
    const view = buildOpportunitiesView(
      response([
        row({
          top_signal: {
            family: "news:mispricing",
            citation: {
              signal_id: "sig-1",
              news_id: null,
              news_url: "https://example.com/n1",
              headline: "Star player questionable",
              model_p: 0.8,
              market_p: 0.5,
            },
          },
        }),
      ]),
    );
    const ev = view.rows[0].evidence;
    expect(ev?.kind).toBe("news");
    expect(view.rows[0].family).toBe("news:mispricing");
    if (ev?.kind === "news") {
      expect(ev.headline).toBe("Star player questionable");
      expect(ev.url).toBe("https://example.com/n1");
      expect(ev.edgeLabel).toBe("+30.0 pts");
    }
  });

  it("keeps evidence null when the row carries no citation", () => {
    const view = buildOpportunitiesView(response([row({ top_signal: null })]));
    expect(view.rows[0].evidence).toBeNull();
    expect(view.rows[0].family).toBeNull();
  });

  it("renders honest placeholders when a yes_price is missing", () => {
    const view = buildOpportunitiesView(response([row({ yes_price: null })]));
    expect(view.rows[0].yesPriceLabel).toBeNull();
  });

  it("formats liquidity compactly", () => {
    const view = buildOpportunitiesView(response([row({ liquidity: 12500 })]));
    expect(view.rows[0].liquidityLabel).toBe("12.5K");
  });
});
