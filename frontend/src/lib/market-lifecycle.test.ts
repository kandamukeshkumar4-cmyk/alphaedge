import { describe, expect, it } from "vitest";

import {
  marketLifecycle,
  marketLifecycleFromDetail,
  marketLifecycleLabel,
  marketCloseCountdown,
} from "./market-lifecycle";
import { isLiveMirror } from "./hero-market";
import { MARKETS, type Market } from "./mock-data";

const NOW = Date.parse("2026-07-14T15:30:00Z");

function market(overrides: Partial<Market> = {}): Market {
  return {
    ...MARKETS[0],
    status: "open",
    endsAt: "2026-07-20T00:00:00Z",
    outcomes: [
      { ...MARKETS[0].outcomes[0], price: 0.5 },
      { ...MARKETS[0].outcomes[1], price: 0.5 },
    ],
    ...overrides,
  };
}

describe("marketLifecycle", () => {
  it("lets resolved status override a future close time", () => {
    expect(marketLifecycle(market({ status: "resolved" }), NOW)).toBe("decided");
  });

  it("labels locked and past-close markets closed", () => {
    expect(
      marketLifecycle(
        market({
          status: "locked",
          outcomes: [
            { ...MARKETS[0].outcomes[0], price: 0 },
            { ...MARKETS[0].outcomes[1], price: 1 },
          ],
        }),
        NOW,
      ),
    ).toBe("closed");
    expect(
      marketLifecycle(market({ endsAt: "2026-07-14T15:29:59Z" }), NOW),
    ).toBe("closed");
  });

  it("uses exact endpoint prices as a defensive decided fallback", () => {
    expect(
      marketLifecycle(
        market({
          outcomes: [
            { ...MARKETS[0].outcomes[0], price: 0 },
            { ...MARKETS[0].outcomes[1], price: 1 },
          ],
        }),
        NOW,
      ),
    ).toBe("decided");
    expect(
      marketLifecycle(
        market({
          outcomes: [
            { ...MARKETS[0].outcomes[0], price: 1 },
            { ...MARKETS[0].outcomes[1], price: 0 },
          ],
        }),
        NOW,
      ),
    ).toBe("decided");
  });

  it("does not call a genuine open longshot decided when it rounds to zero percent", () => {
    expect(
      marketLifecycle(
        market({
          outcomes: [
            { ...MARKETS[0].outcomes[0], price: 0.0045 },
            { ...MARKETS[0].outcomes[1], price: 0.9955 },
          ],
        }),
        NOW,
      ),
    ).toBe("live");
  });

  it("provides explicit user-facing labels", () => {
    expect(marketLifecycleLabel("live")).toBe("LIVE");
    expect(marketLifecycleLabel("closed")).toBe("Closed");
    expect(marketLifecycleLabel("decided")).toBe("Decided");
  });

  it("only shows a current close countdown for a genuinely live future market", () => {
    expect(marketCloseCountdown("live", "2026-07-20T00:00:00Z", NOW)).toBe("5d");
    expect(marketCloseCountdown("closed", "2099-01-01T00:00:00Z", NOW)).toBeNull();
    expect(marketCloseCountdown("decided", "2099-01-01T00:00:00Z", NOW)).toBeNull();
    expect(marketCloseCountdown("live", "2020-01-01T00:00:00Z", NOW)).toBeNull();
    expect(marketCloseCountdown("live", "", NOW)).toBeNull();
    expect(marketCloseCountdown("live", "not-a-date", NOW)).toBeNull();
  });

  it("does not subscribe resolved or closed mirrors as live sources", () => {
    expect(isLiveMirror(market({ source: "polymarket", status: "resolved" }))).toBe(false);
    expect(isLiveMirror(market({ source: "kalshi", status: "locked" }))).toBe(false);
    expect(
      isLiveMirror(
        market({ source: "polymarket", endsAt: "2099-01-01T00:00:00Z" }),
      ),
    ).toBe(true);
  });

  it("uses locked detail status before the real catalog close time loads", () => {
    expect(
      marketLifecycleFromDetail(
        market({ endsAt: "2099-01-01T00:00:00Z" }),
        { status: "locked", outcomes: [{ label: "YES", price: 0.5 }] },
        null,
        NOW,
      ),
    ).toBe("closed");
  });

  it("does not close an API-open market from a stale bundled close date", () => {
    expect(
      marketLifecycleFromDetail(
        market({ endsAt: "2026-06-12T00:00:00Z" }),
        { status: "open", outcomes: [{ label: "YES", price: 0.66 }] },
        null,
        NOW,
      ),
    ).toBe("live");
  });
});
