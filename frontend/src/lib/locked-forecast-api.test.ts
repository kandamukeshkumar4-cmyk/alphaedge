import { describe, expect, it } from "vitest";

import {
  buildLockedForecastView,
  PRE_LOCK_COPY,
  UNAVAILABLE_COPY,
  type LockedForecastResponse,
} from "./locked-forecast-api";

const NOW = Date.parse("2026-07-16T18:00:00Z");

const lockedFixture: LockedForecastResponse = {
  slug: "pm-example",
  locked: true,
  user_probability: 0.62,
  locked_at: "2026-07-16T16:00:00Z",
  market_implied_at_lock: 0.55,
  current_market_probability: 0.58,
  mode: "live",
  provisional: true,
  paper_trading_only: true,
  forecast_id: "11111111-1111-1111-1111-111111111111",
  external_market_id: "22222222-2222-2222-2222-222222222222",
  empty_reason: null,
};

const preLockFixture: LockedForecastResponse = {
  slug: "pm-example",
  locked: false,
  user_probability: null,
  locked_at: null,
  market_implied_at_lock: null,
  current_market_probability: 0.58,
  mode: null,
  provisional: true,
  paper_trading_only: true,
  forecast_id: null,
  external_market_id: null,
  empty_reason: "pre_lock",
};

describe("buildLockedForecastView", () => {
  it("surfaces locked probability, relative lock time, and delta vs market", () => {
    const view = buildLockedForecastView(lockedFixture, { nowMs: NOW });
    expect(view.state).toBe("locked");
    expect(view.lockedProbLabel).toBe("62%");
    expect(view.lockedAtRelative).toBe("2h ago");
    expect(view.currentProbLabel).toBe("58%");
    expect(view.deltaPts).toBe(4);
    expect(view.deltaLabel).toBe("+4 pts vs market");
    expect(view.provisional).toBe(true);
    expect(view.emptyCopy).toBeNull();
  });

  it("uses honest pre-lock copy and never invents a locked %", () => {
    const view = buildLockedForecastView(preLockFixture, { nowMs: NOW });
    expect(view.state).toBe("pre_lock");
    expect(view.lockedProbLabel).toBeNull();
    expect(view.deltaPts).toBeNull();
    expect(view.emptyCopy).toBe(PRE_LOCK_COPY);
    expect(view.currentProbLabel).toBe("58%");
  });

  it("treats locked=true with null user_probability as pre-lock (no fabrication)", () => {
    const view = buildLockedForecastView(
      { ...lockedFixture, user_probability: null },
      { nowMs: NOW },
    );
    expect(view.state).toBe("pre_lock");
    expect(view.lockedProbLabel).toBeNull();
    expect(view.emptyCopy).toBe(PRE_LOCK_COPY);
  });

  it("marks unavailable when API returns null", () => {
    const view = buildLockedForecastView(null);
    expect(view.state).toBe("unavailable");
    expect(view.lockedProbLabel).toBeNull();
    expect(view.emptyCopy).toBe(UNAVAILABLE_COPY);
  });

  it("exposes loading state without fabricating numbers", () => {
    const view = buildLockedForecastView(null, { loading: true });
    expect(view.state).toBe("loading");
    expect(view.lockedProbLabel).toBeNull();
    expect(view.emptyCopy).toBeNull();
  });

  it("formats negative delta when market is above lock", () => {
    const view = buildLockedForecastView(
      { ...lockedFixture, user_probability: 0.5, current_market_probability: 0.58 },
      { nowMs: NOW },
    );
    expect(view.deltaPts).toBe(-8);
    expect(view.deltaLabel).toBe("-8 pts vs market");
  });
});
