import { describe, expect, it } from "vitest";

import type { SignalEventItem } from "./activity-api";
import { MARKETS } from "./mock-data";
import {
  buildSignalRailRows,
  dedupeSignalEvents,
  relativeSignalAge,
  tickerFreshnessWindowMs,
} from "./signal-rail";

const NOW = Date.parse("2026-07-14T01:20:00Z");

function event(overrides: Partial<SignalEventItem>): SignalEventItem {
  return {
    id: overrides.id ?? "sig-1",
    signal_type: overrides.signal_type ?? "delta:price_jump",
    platform: overrides.platform ?? "polymarket.gamma",
    market_id: overrides.market_id ?? "pm-alpha",
    market_title: overrides.market_title,
    headline_eligible: false,
    payload: overrides.payload ?? {
      kind: "price_jump",
      direction: "up",
      magnitude: 0.02,
      detail: { bps: 200 },
    },
    created_at: overrides.created_at ?? "2026-07-14T01:18:00Z",
  };
}

describe("signal rail view model", () => {
  it("renders a real title, signed magnitude, direction, and relative age", () => {
    const rows = buildSignalRailRows(
      [event({ market_title: "Will OpenAI announce earbuds in 2026?" })],
      [],
      { nowMs: NOW },
    );

    expect(rows[0]).toMatchObject({
      title: "Will OpenAI announce earbuds in 2026?",
      direction: "UP",
      label: "Price Jump",
      value: "+200 bps",
      age: "2m ago",
    });
  });

  it("dedupes identical semantic events but keeps an opposite move", () => {
    const duplicate = event({
      id: "duplicate",
      created_at: "2026-07-14T01:15:00Z",
    });
    const down = event({
      id: "down",
      created_at: "2026-07-14T01:14:00Z",
      payload: {
        kind: "price_jump",
        direction: "down",
        magnitude: 0.02,
        detail: { bps: 200 },
      },
    });

    expect(dedupeSignalEvents([event({ id: "newest" }), duplicate, down]).map((e) => e.id))
      .toEqual(["newest", "down"]);
  });

  it("sorts events newest-first before deduping", () => {
    expect(dedupeSignalEvents([
      event({ id: "old", created_at: "2026-07-14T01:00:00Z" }),
      event({ id: "new", created_at: "2026-07-14T01:18:00Z" }),
    ], 0).map((row) => row.id)).toEqual(["new", "old"]);
  });

  it("drops ticker rows outside the configured freshness window", () => {
    const rows = buildSignalRailRows([
      event({ id: "stale", created_at: "2026-07-11T01:20:00Z" }),
      event({ id: "fresh", created_at: "2026-07-14T00:20:00Z" }),
    ], [], { nowMs: NOW, maxAgeMs: tickerFreshnessWindowMs(), limit: 10 });

    expect(rows.map((row) => row.key)).toEqual(["fresh"]);
    expect(tickerFreshnessWindowMs("12")).toBe(12 * 60 * 60 * 1000);
    expect(tickerFreshnessWindowMs("invalid")).toBe(48 * 60 * 60 * 1000);
  });

  it("falls back to the catalog title and an honest non-numeric value", () => {
    const market = { ...MARKETS[0], slug: "pm-alpha", title: "Alpha market" };
    const rows = buildSignalRailRows(
      [event({ signal_type: "alignment", payload: { direction: "up" } })],
      [market],
      { nowMs: NOW },
    );

    expect(rows[0]).toMatchObject({ title: "Alpha market", value: "Observed" });
    expect(rows[0].value).not.toBe("—");
  });

  it("formats sub-minute and invalid ages without inventing a timestamp", () => {
    expect(relativeSignalAge("2026-07-14T01:19:45Z", NOW)).toBe("15s ago");
    expect(relativeSignalAge("not-a-date", NOW)).toBe("time unknown");
  });
});
