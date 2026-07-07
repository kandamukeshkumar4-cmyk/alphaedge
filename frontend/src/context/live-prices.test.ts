import { describe, expect, it } from "vitest";

import {
  collectPrioritySlugs,
  FeedMultiplexer,
  selectFeedTick,
  selectPollSlugs,
  SubscriptionRegistry,
  type FeedSocket,
} from "./live-prices";
import type { Market } from "@/lib/mock-data";

/** In-memory fake of the browser WebSocket subset the multiplexer uses. */
class FakeSocket implements FeedSocket {
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  close() {
    this.closed = true;
  }
  /** Simulate a server frame arriving. */
  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

function kalshiMarket(slug: string, outcomes: { id: string; price: number }[]): Market {
  return {
    id: slug,
    slug,
    category: "Sports",
    icon: "⚽",
    title: slug,
    question: slug,
    endsAt: "2026-06-27T22:00:00Z",
    volume: 1_000_000,
    traders: 0,
    marketCount: outcomes.length,
    trendDelta: 0,
    source: "kalshi",
    outcomes: outcomes.map((o) => ({
      id: o.id,
      label: o.id.toUpperCase(),
      emoji: "⚽",
      price: o.price,
      prevPrice: o.price,
      tone: "primary" as const,
    })),
    forecast: { prob: 0.5, confidence: 0.5, edge: 0, brier: 0.2, reasoning: "" },
    bids: [],
    asks: [],
    description: "",
    resolution: "",
    trades: [],
    holders: [],
    comments: [],
    seed: 1,
  };
}

describe("SubscriptionRegistry — one poll loop with multiple subscribers", () => {
  it("collapses many subscribers per slug into one slot (one fetch per slug, one poll loop)", () => {
    const reg = new SubscriptionRegistry();

    // Three cards subscribe; slug-a has two independent subscribers.
    const unsubA1 = reg.subscribe("slug-a");
    const unsubA2 = reg.subscribe("slug-a");
    const unsubB = reg.subscribe("slug-b");

    // 3 subscribers, but only 2 slug slots → the single poll loop fetches each
    // slug once, not once per subscriber (no per-card connection/poll).
    expect(reg.size()).toBe(2);
    expect(reg.slugs().sort()).toEqual(["slug-a", "slug-b"]);

    // Dropping one subscriber for slug-a keeps the slot alive (refcount > 0).
    unsubA1();
    expect(reg.has("slug-a")).toBe(true);
    expect(reg.size()).toBe(2);

    // Last subscriber for slug-a drops → slot removed from the poll list.
    unsubA2();
    expect(reg.has("slug-a")).toBe(false);
    expect(reg.slugs()).toEqual(["slug-b"]);

    unsubB();
    expect(reg.size()).toBe(0);
  });

  it("ignores empty slugs", () => {
    const reg = new SubscriptionRegistry();
    const unsub = reg.subscribe("");
    expect(reg.size()).toBe(0);
    unsub();
    expect(reg.size()).toBe(0);
  });
});

describe("selectPollSlugs — per-slug subscription filtering", () => {
  it("polls only priority + subscribed slugs (deduped), never the full catalog", () => {
    const priority = ["hero-yes", "hero-no"];
    const subscribed = ["hero-yes", "detail-a", "detail-b"];

    const slugs = selectPollSlugs(priority, subscribed);

    // Deduped: hero-yes appears in both but is polled once.
    expect(slugs).toHaveLength(4);
    expect(slugs.sort()).toEqual(["detail-a", "detail-b", "hero-no", "hero-yes"]);

    // Slugs that are neither priority nor subscribed are NOT polled — the old
    // behavior fetched the full market catalog; this must not.
    expect(slugs).not.toContain("unrelated-market");
    expect(slugs).not.toContain("");
  });

  it("returns only priority slugs when nothing is dynamically subscribed", () => {
    const slugs = selectPollSlugs(["p1", "p2"], []);
    expect(slugs).toEqual(["p1", "p2"]);
  });

  it("returns only subscribed slugs when there are no priority slugs", () => {
    const slugs = selectPollSlugs([], ["s1", "s2"]);
    expect(slugs.sort()).toEqual(["s1", "s2"]);
  });

  it("collectPrioritySlugs stays bounded and only mirrors live-market outcome slugs", () => {
    const hero = [
      kalshiMarket("ks-kxwcgame-26jun13bramar-bra", [
        { id: "yes", price: 0.59 },
        { id: "no", price: 0.41 },
      ]),
    ];
    const slugs = collectPrioritySlugs(hero, [], 24);
    expect(slugs.length).toBeGreaterThan(0);
    expect(slugs.length).toBeLessThanOrEqual(24);
    expect(slugs).toContain("ks-kxwcgame-26jun13bramar-bra");
  });
});

describe("selectFeedTick — per-slug filtering of the multiplexed feed", () => {
  const active = new Set(["a", "b"]);
  const isActive = (s: string) => active.has(s);

  it("accepts a market.tick frame for an active slug", () => {
    expect(selectFeedTick({ channel: "market.tick", slug: "a", yes: 0.6, ts: 5 }, isActive)).toEqual({
      slug: "a",
      yes: 0.6,
      ts: 5,
    });
  });

  it("drops ticks for slugs nobody is subscribed to", () => {
    expect(selectFeedTick({ channel: "market.tick", slug: "z", yes: 0.6 }, isActive)).toBeNull();
  });

  it("drops non-tick channels multiplexed on the same socket (briefs/alerts/system)", () => {
    expect(selectFeedTick({ channel: "briefs", slug: "a", yes: 0.6 }, isActive)).toBeNull();
    expect(selectFeedTick({ channel: "system", connected: true }, isActive)).toBeNull();
  });

  it("rejects malformed frames without throwing", () => {
    expect(selectFeedTick(null, isActive)).toBeNull();
    expect(selectFeedTick({ channel: "market.tick", slug: "a" }, isActive)).toBeNull();
    expect(selectFeedTick({ channel: "market.tick", yes: 0.6 }, isActive)).toBeNull();
  });
});

describe("FeedMultiplexer — single connection, many subscribers", () => {
  it("opens ONE socket regardless of how many slugs are active, and routes ticks per-slug", () => {
    const sockets: FakeSocket[] = [];
    const active = new Set<string>();
    const ticks: { slug: string; yes: number }[] = [];

    const mux = new FeedMultiplexer(
      () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s;
      },
      (t) => ticks.push({ slug: t.slug, yes: t.yes }),
      (slug) => active.has(slug),
    );
    mux.start();
    // Idempotent: a second start() must not open a second connection.
    mux.start();

    // Three "cards" become active — still one shared connection.
    active.add("a");
    active.add("b");
    active.add("c");
    expect(mux.connectionCount).toBe(1);
    expect(sockets).toHaveLength(1);

    const sock = sockets[0];
    sock.onopen?.();
    sock.emit({ channel: "market.tick", slug: "a", yes: 0.55, ts: 1 });
    sock.emit({ channel: "market.tick", slug: "b", yes: 0.42, ts: 2 });
    sock.emit({ channel: "market.tick", slug: "unsubscribed", yes: 0.9, ts: 3 });
    sock.emit({ channel: "briefs", slug: "a", headline: "noise" });

    // Only the two active, real ticks landed — one connection fed all subscribers.
    expect(ticks).toEqual([
      { slug: "a", yes: 0.55 },
      { slug: "b", yes: 0.42 },
    ]);

    mux.stop();
    expect(sock.closed).toBe(true);
  });

  it("does not open a connection when the socket factory yields null (no backend)", () => {
    const mux = new FeedMultiplexer(
      () => null,
      () => {},
      () => true,
    );
    mux.start();
    expect(mux.connectionCount).toBe(0);
  });
});
