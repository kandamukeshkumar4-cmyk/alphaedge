import { describe, expect, it } from "vitest";

import { liveNo, liveYes, parsePriceFrame } from "./useMarketPrice";

/**
 * Loop117 (D1b/D19) regression: `/api/v1/ws/prices` publishes
 * `{slug, yes_price, ts}`. The hook used to read `d.yes`, so every tick set
 * `{yes: undefined, connected: true}` and PriceChart then wrote NaN into
 * lightweight-charts — which asserts, throws inside a React effect and
 * unmounts the whole market page (detached Paper buy button, missing chart).
 * In production the assert is stripped and the header renders `NaN¢`.
 */
describe("parsePriceFrame", () => {
  it("reads the yes_price field the price socket actually publishes", () => {
    expect(
      parsePriceFrame({ slug: "nba-2025-01-15-lal-bos", yes_price: 0.65, ts: 1780434000 }),
    ).toEqual({ yes: 0.65, no: 0.35, ts: 1780434000 });
  });

  it("still accepts a legacy `yes` field", () => {
    expect(parsePriceFrame({ yes: 0.4, ts: 12 })).toEqual({
      yes: 0.4,
      no: 0.6,
      ts: 12,
    });
  });

  it("rejects frames with no usable price instead of emitting NaN", () => {
    for (const frame of [
      { slug: "x", ts: 1 },
      { yes_price: null, ts: 1 },
      { yes_price: "abc", ts: 1 },
      { yes_price: Number.NaN, ts: 1 },
      { yes_price: 1.4, ts: 1 },
      { yes_price: -0.2, ts: 1 },
      { keepalive: true },
      null,
    ]) {
      expect(parsePriceFrame(frame)).toBeNull();
    }
  });

  it("defaults a missing timestamp rather than producing NaN", () => {
    const tick = parsePriceFrame({ yes_price: 0.5 });
    expect(tick).not.toBeNull();
    expect(Number.isFinite(tick!.ts)).toBe(true);
  });
});

describe("liveYes / liveNo", () => {
  it("are null unless a usable tick has arrived", () => {
    expect(liveYes({ yes: null, no: null, ts: null, connected: false })).toBeNull();
    expect(liveYes({ yes: 0.6, no: 0.4, ts: 1, connected: false })).toBeNull();
    expect(liveYes({ yes: 0, no: 1, ts: 1, connected: true })).toBeNull();
    expect(liveNo({ yes: 1, no: 0, ts: 1, connected: true })).toBeNull();
  });

  it("pass a usable tick through", () => {
    const state = { yes: 0.65, no: 0.35, ts: 1, connected: true };
    expect(liveYes(state)).toBe(0.65);
    expect(liveNo(state)).toBe(0.35);
  });
});
