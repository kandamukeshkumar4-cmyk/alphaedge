import { describe, expect, it } from "vitest";
import {
  alertFamilies,
  buildAlertGroups,
  newestAlertTs,
  normalizeAlertItems,
  relativeTime,
  unreadAlertCount,
  type AlertEventItem,
} from "./alerts-api";

const NOW = Date.parse("2026-07-10T18:00:00Z");

const ITEMS: AlertEventItem[] = [
  {
    id: "1",
    signal_type: "news:mispricing",
    platform: "polymarket",
    market_id: "pm-lal-bos",
    payload: { headline: "Star out", model_p: 0.62, market_p: 0.5, gap: 0.12, news_url: "http://x" },
    created_at: "2026-07-10T17:55:00Z",
  },
  {
    id: "2",
    signal_type: "anomaly:unusual_flow",
    platform: "polymarket",
    market_id: "pm-lal-bos",
    payload: { catalyst: "none_found" },
    created_at: "2026-07-10T17:40:00Z",
  },
  {
    id: "3",
    signal_type: "screener:value",
    platform: "kalshi",
    market_id: "ks-other",
    payload: {},
    created_at: "2026-07-10T16:00:00Z",
  },
];

describe("relativeTime", () => {
  it("formats minutes and hours relative to now", () => {
    expect(relativeTime("2026-07-10T17:55:00Z", NOW)).toBe("5m ago");
    expect(relativeTime("2026-07-10T16:00:00Z", NOW)).toBe("2h ago");
    expect(relativeTime("not-a-date", NOW)).toBe("");
  });
});

describe("buildAlertGroups", () => {
  it("groups by market, newest group first, rows newest first", () => {
    const groups = buildAlertGroups(ITEMS, "all", NOW);
    expect(groups).toHaveLength(2);
    expect(groups[0].slug).toBe("pm-lal-bos"); // most recent event
    expect(groups[0].count).toBe(2);
    expect(groups[0].rows[0].id).toBe("1");
    expect(groups[0].families).toEqual(expect.arrayContaining(["news", "anomaly"]));
  });

  it("attaches evidence for news + catalyst rows", () => {
    const [first] = buildAlertGroups(ITEMS, "all", NOW);
    const news = first.rows.find((r) => r.family === "news");
    expect(news?.evidence?.kind).toBe("news");
    const flow = first.rows.find((r) => r.family === "anomaly");
    expect(flow?.evidence?.kind).toBe("catalyst");
  });

  it("filters to a single family", () => {
    const groups = buildAlertGroups(ITEMS, "screener", NOW);
    expect(groups).toHaveLength(1);
    expect(groups[0].slug).toBe("ks-other");
  });

  it("returns [] for no items", () => {
    expect(buildAlertGroups([], "all", NOW)).toEqual([]);
  });
});

describe("normalizeAlertItems", () => {
  it("maps the feed `slug` to `market_id` and folds citation into payload", () => {
    const [item] = normalizeAlertItems([
      {
        id: "9",
        signal_type: "news:mispricing",
        platform: "polymarket",
        slug: "pm-lal-bos",
        payload: { model_p: 0.6 },
        citation: { headline: "Star out", news_url: "http://x", market_p: 0.5 },
        created_at: "2026-07-10T17:00:00Z",
      },
    ]);
    expect(item.market_id).toBe("pm-lal-bos");
    // payload wins over citation on conflicts, citation fills the gaps.
    expect(item.payload).toMatchObject({ model_p: 0.6, headline: "Star out", market_p: 0.5 });
    // it renders through buildAlertGroups (slug-only feed previously grouped empty).
    const groups = buildAlertGroups([item], "all", NOW);
    expect(groups).toHaveLength(1);
    expect(groups[0].rows[0].evidence?.kind).toBe("news");
  });

  it("prefers an explicit market_id when both are present", () => {
    const [item] = normalizeAlertItems([
      { id: "1", slug: "s", market_id: "m", created_at: "2026-07-10T17:00:00Z" },
    ]);
    expect(item.market_id).toBe("m");
  });

  it("drops items missing id/market/timestamp and tolerates non-arrays", () => {
    expect(normalizeAlertItems(null)).toEqual([]);
    expect(
      normalizeAlertItems([
        { signal_type: "arb", slug: "s", created_at: "2026-07-10T17:00:00Z" },
        { id: "2", created_at: "2026-07-10T17:00:00Z" },
        { id: "3", slug: "s3" },
      ]),
    ).toEqual([]);
  });
});

describe("alertFamilies", () => {
  it("lists distinct families present", () => {
    expect(alertFamilies(ITEMS).sort()).toEqual(["anomaly", "news", "screener"]);
  });
});

describe("unreadAlertCount / newestAlertTs", () => {
  it("counts items after the last-seen ts", () => {
    const cutoff = Date.parse("2026-07-10T17:45:00Z");
    expect(unreadAlertCount(ITEMS, cutoff)).toBe(1); // only item 1 (17:55)
    expect(unreadAlertCount(ITEMS, 0)).toBe(3);
  });

  it("finds the newest timestamp", () => {
    expect(newestAlertTs(ITEMS)).toBe(Date.parse("2026-07-10T17:55:00Z"));
    expect(newestAlertTs([])).toBe(0);
  });
});
