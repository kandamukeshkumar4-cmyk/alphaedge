import { describe, expect, it } from "vitest";

import { parseSocketMessage } from "./useLiveMarket";

/**
 * Loop117 follow-up: useLiveMarket had its own copy of the price-frame guard
 * that read `d.yes` while `/api/v1/ws/prices` publishes `{slug, yes_price, ts}`,
 * so every WS tick was dropped and only the 1s HTTP poll updated the hero.
 * The hook now parses through the shared parsePriceFrame; this covers the
 * socket-message seam (raw string → validated tick).
 */
describe("parseSocketMessage", () => {
  it("accepts the frame the price socket actually publishes", () => {
    expect(
      parseSocketMessage(
        JSON.stringify({ slug: "nba-2025-01-15-lal-bos", yes_price: 0.65, ts: 1780434000 }),
      ),
    ).toEqual({ yes: 0.65, no: 0.35, ts: 1780434000 });
  });

  it("still accepts a legacy `yes` field", () => {
    expect(parseSocketMessage(JSON.stringify({ yes: 0.4, ts: 12 }))).toEqual({
      yes: 0.4,
      no: 0.6,
      ts: 12,
    });
  });

  it("drops keepalives and frames without a usable price", () => {
    for (const frame of [
      { keepalive: true },
      { slug: "x", ts: 1 },
      { yes_price: null, ts: 1 },
      { yes_price: "abc", ts: 1 },
      { yes_price: 1.4, ts: 1 },
      { yes_price: -0.2, ts: 1 },
    ]) {
      expect(parseSocketMessage(JSON.stringify(frame))).toBeNull();
    }
  });

  it("drops malformed payloads instead of throwing", () => {
    expect(parseSocketMessage("not json{")).toBeNull();
    expect(parseSocketMessage(undefined)).toBeNull();
  });

  it("defaults a missing timestamp rather than producing NaN", () => {
    const tick = parseSocketMessage(JSON.stringify({ yes_price: 0.5 }));
    expect(tick).not.toBeNull();
    expect(Number.isFinite(tick!.ts)).toBe(true);
  });
});
