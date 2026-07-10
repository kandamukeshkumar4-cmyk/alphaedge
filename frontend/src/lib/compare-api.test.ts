import { describe, expect, it } from "vitest";
import {
  buildCompareView,
  parseCompareSlugs,
  type CompareEntry,
  type CompareResponse,
} from "./compare-api";

function entry(overrides: Partial<CompareEntry>): CompareEntry {
  return {
    found: true,
    slug: "mkt-a",
    title: "Market A",
    yes_price: 0.5,
    edge: { model_p: 0.62, market_p: 0.5, edge: 0.12 },
    top_signal: null,
    arb_matched: false,
    smart_money_note: null,
    ...overrides,
  };
}

function response(overrides: Partial<CompareResponse>): CompareResponse {
  const entries = overrides.entries ?? [entry({})];
  return {
    entries,
    count: entries.length,
    requested: entries.map((e) => e.slug ?? ""),
    clamped: false,
    max_slugs: 4,
    paper_trading_only: true,
    signal_only: true,
    disclaimer: "Market comparison — NOT an order feed.",
    generated_at: "2026-07-10T18:00:00Z",
    ...overrides,
  };
}

describe("parseCompareSlugs", () => {
  it("returns [] for blank / null input", () => {
    expect(parseCompareSlugs(null)).toEqual([]);
    expect(parseCompareSlugs("")).toEqual([]);
    expect(parseCompareSlugs("  ,  ")).toEqual([]);
  });

  it("trims, drops blanks and duplicates, preserving order", () => {
    expect(parseCompareSlugs("a, b ,,a,c")).toEqual(["a", "b", "c"]);
  });

  it("clamps to the first 4 slugs", () => {
    expect(parseCompareSlugs("a,b,c,d,e,f")).toEqual(["a", "b", "c", "d"]);
  });
});

describe("buildCompareView", () => {
  it("marks the view unreachable for a null response", () => {
    const view = buildCompareView(null);
    expect(view.reachable).toBe(false);
    expect(view.columns).toEqual([]);
    expect(view.requested).toEqual([]);
    expect(view.clamped).toBe(false);
    expect(view.maxSlugs).toBe(4);
  });

  it("is reachable but empty for a no-slugs response", () => {
    const view = buildCompareView(response({ entries: [], requested: [], count: 0 }));
    expect(view.reachable).toBe(true);
    expect(view.columns).toEqual([]);
  });

  it("builds a found column with an edge one-liner reusing the share-snapshot view", () => {
    const view = buildCompareView(
      response({
        entries: [
          entry({ slug: "mkt-a", edge: { model_p: 0.62, market_p: 0.5, edge: 0.12 } }),
        ],
      }),
    );
    const col = view.columns[0];
    expect(col.found).toBe(true);
    expect(col.requestedSlug).toBe("mkt-a");
    expect(col.yesLabel).toBe("50%");
    expect(col.edgeLabel).toBe("+12.0 pts");
    expect(col.edgeTone).toBe("up");
    expect(col.modelLabel).toBe("62%");
    expect(col.marketLabel).toBe("50%");
    expect(col.yesPrice).toBeCloseTo(0.5);
  });

  it("degrades an unknown slug to an honest per-column not-found", () => {
    const view = buildCompareView(
      response({
        entries: [
          entry({ found: true, slug: "known" }),
          entry({
            found: false,
            slug: "missing",
            title: null,
            yes_price: null,
            edge: null,
            top_signal: null,
          }),
        ],
        requested: ["known", "missing"],
      }),
    );
    expect(view.columns).toHaveLength(2);
    expect(view.columns[0].found).toBe(true);
    expect(view.columns[1].found).toBe(false);
    expect(view.columns[1].requestedSlug).toBe("missing");
    expect(view.columns[1].edgeLabel).toBeNull();
    expect(view.columns[1].yesLabel).toBeNull();
  });

  it("surfaces the clamp flag and echoes the requested slugs", () => {
    const view = buildCompareView(
      response({
        entries: [entry({ slug: "a" }), entry({ slug: "b" })],
        requested: ["a", "b", "c", "d"],
        clamped: true,
      }),
    );
    expect(view.clamped).toBe(true);
    expect(view.requested).toEqual(["a", "b", "c", "d"]);
  });

  it("carries the arb flag and smart-money note through a column", () => {
    const view = buildCompareView(
      response({
        entries: [
          entry({ arb_matched: true, smart_money_note: "Concentrated YES buying" }),
        ],
      }),
    );
    expect(view.columns[0].arbMatched).toBe(true);
    expect(view.columns[0].smartMoneyNote).toBe("Concentrated YES buying");
  });

  it("uses the backend disclaimer when present", () => {
    const view = buildCompareView(response({}));
    expect(view.disclaimer).toContain("NOT an order feed");
  });
});
