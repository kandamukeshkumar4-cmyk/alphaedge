import { describe, expect, it } from "vitest";

import type { FeedItem } from "./feed-api";
import { normalizeFeedItems } from "./feed-freshness";

function item(overrides: Partial<FeedItem> = {}): FeedItem {
  return {
    id: overrides.id ?? "event-new",
    item_type: overrides.item_type ?? "signal",
    market_slug: overrides.market_slug ?? "pm-alpha",
    market_title: overrides.market_title ?? "Alpha",
    platform: overrides.platform ?? "polymarket.gamma",
    summary: overrides.summary ?? "Price jump",
    confidence: overrides.confidence ?? null,
    target: overrides.target ?? null,
    timestamp: overrides.timestamp ?? "2026-07-14T02:00:00Z",
    payload: overrides.payload ?? {
      kind: "price_jump",
      direction: "up",
      magnitude: 0.02,
      detail: { bps: 200 },
    },
  };
}

describe("feed freshness normalization", () => {
  it("orders mixed REST and WebSocket items newest-first", () => {
    const rows = normalizeFeedItems([
      item({ id: "old", timestamp: "2026-07-14T01:00:00Z" }),
      item({ id: "new", timestamp: "2026-07-14T03:00:00Z" }),
      item({ id: "middle", timestamp: "2026-07-14T02:00:00Z" }),
    ], { dedupeWindowMs: 0 });

    expect(rows.map((row) => row.id)).toEqual(["new", "middle", "old"]);
  });

  it("dedupes semantic repeats but preserves opposite price moves", () => {
    const duplicate = item({ id: "duplicate", timestamp: "2026-07-14T01:55:00Z" });
    const down = item({
      id: "down",
      timestamp: "2026-07-14T01:54:00Z",
      payload: {
        kind: "price_jump",
        direction: "down",
        magnitude: 0.02,
        detail: { bps: 200 },
      },
    });

    expect(normalizeFeedItems([duplicate, down, item()]).map((row) => row.id))
      .toEqual(["event-new", "down"]);
  });

  it("keeps the same semantic event when it recurs outside the window", () => {
    const rows = normalizeFeedItems([
      item(),
      item({ id: "later-observation", timestamp: "2026-07-14T01:40:00Z" }),
    ]);

    expect(rows).toHaveLength(2);
  });
});
