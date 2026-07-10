import { describe, expect, it } from "vitest";
import { buildHomeView, buildMarketRows, buildSignalRows, type HomeResponse } from "./home-api";

const NOW = Date.parse("2026-07-10T12:00:00Z");

const NEWS_SIGNAL = {
  id: "sig-1",
  signal_type: "news:mispricing",
  platform: "seed",
  slug: "nba-2025-01-15-lal-bos",
  created_at: "2026-07-10T11:30:00Z",
  citation: {
    news_url: "https://example.com/n1",
    headline: "Star player questionable",
    model_p: 0.62,
    market_p: 0.5,
  },
};

const OLDER_SIGNAL = {
  id: "sig-0",
  signal_type: "anomaly:unusual_flow",
  platform: "seed",
  slug: "nba-2025-01-16-gsw-mia",
  created_at: "2026-07-10T09:00:00Z",
  payload: { catalyst: "none_found" },
};

const ANON: HomeResponse = {
  authenticated: false,
  signals: [OLDER_SIGNAL, NEWS_SIGNAL],
  digest: { families: { "news:mispricing": 1, arb: 1 }, total: 2, window: "24h" },
  model_ab: {
    resolved_count: 42,
    ab_threshold: 100,
    ab_ready: false,
    model_default: "xgboost",
    lightgbm_available: true,
    applied: false,
  },
  top_markets: [
    { slug: "b", title: "B", category: "Sports", volume: 9000, yes_price: 0.54, status: "open" },
    { slug: "a", title: "A", category: "Politics", volume: 4000, yes_price: null, status: "open" },
  ],
  watchlist_count: null,
  watchlist_alerts: [],
  disclaimer: "Personalized intelligence home — test.",
};

describe("buildSignalRows", () => {
  it("normalizes, sorts newest-first, and carries H03 citation evidence", () => {
    const rows = buildSignalRows([OLDER_SIGNAL, NEWS_SIGNAL], NOW);
    expect(rows.map((r) => r.id)).toEqual(["sig-1", "sig-0"]); // newest first
    const news = rows[0];
    expect(news.slug).toBe("nba-2025-01-15-lal-bos");
    expect(news.familyLabel).toBe("News");
    expect(news.evidence?.kind).toBe("news");
    if (news.evidence?.kind === "news") {
      expect(news.evidence.headline).toBe("Star player questionable");
      expect(news.evidence.url).toBe("https://example.com/n1");
    }
    expect(rows[1].evidence?.kind).toBe("catalyst");
  });

  it("is an honest empty for null/[]", () => {
    expect(buildSignalRows(null)).toEqual([]);
    expect(buildSignalRows([])).toEqual([]);
  });
});

describe("buildMarketRows", () => {
  it("formats compact volume and YES%, honest dash / null for missing", () => {
    const rows = buildMarketRows(ANON.top_markets);
    expect(rows).toHaveLength(2);
    expect(rows[0].yesLabel).toBe("54%");
    expect(rows[0].volumeLabel).toContain("9");
    expect(rows[1].yesLabel).toBeNull(); // no odds snapshot
  });

  it("drops rows without a slug and falls back title→slug", () => {
    const rows = buildMarketRows([{ title: "no slug" }, { slug: "x", volume: 10 }]);
    expect(rows).toHaveLength(1);
    expect(rows[0].title).toBe("x");
    expect(rows[0].volumeLabel).toContain("10");
  });
});

describe("buildHomeView — anon", () => {
  it("composes the four non-personal sections and nulls the personal ones", () => {
    const view = buildHomeView(ANON, NOW);
    expect(view.reachable).toBe(true);
    expect(view.authenticated).toBe(false);
    expect(view.signals).toHaveLength(2);
    expect(view.digest.total).toBe(2);
    expect(view.topMarkets).toHaveLength(2);
    // model A/B readiness: progress toward threshold, never a claimed winner.
    expect(view.modelAb.state).toBe("not-ready");
    expect(view.modelAb.resolvedLabel).toBe("42 / 100 resolved");
    expect(view.modelAb.winnerLabel).toBeNull();
    expect(view.watchlistCount).toBeNull();
    expect(view.watchlistAlerts).toEqual([]);
  });
});

describe("buildHomeView — authed enrichment", () => {
  it("carries the watchlist count and watchlist-scoped alerts", () => {
    const view = buildHomeView(
      { ...ANON, authenticated: true, watchlist_count: 3, watchlist_alerts: [NEWS_SIGNAL] },
      NOW,
    );
    expect(view.authenticated).toBe(true);
    expect(view.watchlistCount).toBe(3);
    expect(view.watchlistAlerts).toHaveLength(1);
    expect(view.watchlistAlerts[0].slug).toBe("nba-2025-01-15-lal-bos");
  });
});

describe("buildHomeView — unreachable + honest empty", () => {
  it("marks unreachable for a null response", () => {
    const view = buildHomeView(null);
    expect(view.reachable).toBe(false);
    expect(view.signals).toEqual([]);
    expect(view.topMarkets).toEqual([]);
    expect(view.watchlistCount).toBeNull();
  });

  it("is an honest empty for an empty DB (200 with empty sections)", () => {
    const view = buildHomeView(
      {
        authenticated: false,
        signals: [],
        digest: { families: {}, total: 0, window: "24h" },
        model_ab: { resolved_count: 0, ab_threshold: 50, ab_ready: false, model_default: "xgboost" },
        top_markets: [],
        watchlist_count: null,
        watchlist_alerts: [],
      },
      NOW,
    );
    expect(view.reachable).toBe(true);
    expect(view.signals).toEqual([]);
    expect(view.digest.empty).toBe(true);
    expect(view.topMarkets).toEqual([]);
  });
});
