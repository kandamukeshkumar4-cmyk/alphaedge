import { describe, expect, it } from "vitest";
import { buildShareSnapshotView, type ShareSnapshotResponse } from "./share-snapshot-api";

const NOW = Date.parse("2026-07-10T12:00:00Z");

const KNOWN: ShareSnapshotResponse = {
  found: true,
  slug: "nba-2025-01-15-lal-bos",
  title: "Lakers vs Celtics",
  yes_price: 0.54,
  edge: { model_p: 0.62, market_p: 0.5, edge: 0.12 },
  top_signal: {
    family: "news:mispricing",
    signal_type: "news:mispricing",
    created_at: "2026-07-10T11:30:00Z",
    citation: {
      news_url: "https://example.com/n1",
      headline: "Star player questionable",
      model_p: 0.62,
      market_p: 0.5,
    },
  },
  arb_matched: false,
  smart_money_note: "Top 5 wallets hold 40% of open interest; 2 recent large flow(s).",
  cached: false,
  disclaimer: "Shareable research snapshot — test.",
};

describe("buildShareSnapshotView — known slug", () => {
  it("formats price, edge one-liner, and top-signal citation evidence", () => {
    const view = buildShareSnapshotView(KNOWN, NOW);
    expect(view.reachable).toBe(true);
    expect(view.found).toBe(true);
    expect(view.title).toBe("Lakers vs Celtics");
    expect(view.yesLabel).toBe("54%");
    expect(view.modelLabel).toBe("62%");
    expect(view.marketLabel).toBe("50%");
    expect(view.edgeLabel).toBe("+12.0 pts");
    expect(view.edgeTone).toBe("up");
    expect(view.smartMoneyNote).toContain("40%");
    expect(view.topSignal?.familyLabel).toBe("News");
    expect(view.topSignal?.evidence?.kind).toBe("news");
    if (view.topSignal?.evidence?.kind === "news") {
      expect(view.topSignal.evidence.headline).toBe("Star player questionable");
      expect(view.topSignal.evidence.url).toBe("https://example.com/n1");
    }
  });

  it("negative edge is toned down; missing edge/signal degrade to null", () => {
    const view = buildShareSnapshotView(
      {
        found: true,
        slug: "x",
        title: "X",
        yes_price: null,
        edge: { model_p: 0.4, market_p: 0.55, edge: -0.15 },
        top_signal: null,
        arb_matched: true,
        smart_money_note: null,
      },
      NOW,
    );
    expect(view.yesLabel).toBeNull();
    expect(view.edgeLabel).toBe("-15.0 pts");
    expect(view.edgeTone).toBe("down");
    expect(view.topSignal).toBeNull();
    expect(view.arbMatched).toBe(true);
    expect(view.smartMoneyNote).toBeNull();
  });
});

describe("buildShareSnapshotView — unknown slug (honest 200)", () => {
  it("is reachable but not found, with everything nulled", () => {
    const view = buildShareSnapshotView(
      { found: false, slug: "nope", title: null, yes_price: null, edge: null, top_signal: null, arb_matched: false, smart_money_note: null },
      NOW,
    );
    expect(view.reachable).toBe(true);
    expect(view.found).toBe(false);
    expect(view.slug).toBe("nope");
    expect(view.title).toBe("nope"); // title falls back to slug
    expect(view.edgeLabel).toBeNull();
    expect(view.topSignal).toBeNull();
  });
});

describe("buildShareSnapshotView — unreachable", () => {
  it("marks unreachable for a null response", () => {
    const view = buildShareSnapshotView(null);
    expect(view.reachable).toBe(false);
    expect(view.found).toBe(false);
    expect(view.edgeLabel).toBeNull();
  });
});
