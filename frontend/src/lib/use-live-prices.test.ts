import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createVisibilityPoller, mockPaperPrice } from "./use-live-prices";

// Loop V90 (C3) — pause-on-hidden polling logic with mocked visibility.
// The scheduler is framework-free, so fake timers + a mutable `hidden` flag
// drive it exactly the way document.hidden drives the React hook.
describe("createVisibilityPoller (pause-on-hidden)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("ticks every interval while visible", () => {
    let hidden = false;
    const onTick = vi.fn();
    const poller = createVisibilityPoller({
      intervalMs: 15_000,
      isHidden: () => hidden,
      onTick,
    });

    poller.start();
    expect(poller.isRunning()).toBe(true);

    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(30_000);
    expect(onTick).toHaveBeenCalledTimes(3);

    poller.stop();
    vi.advanceTimersByTime(45_000);
    expect(onTick).toHaveBeenCalledTimes(3);
    expect(poller.isRunning()).toBe(false);
  });

  it("pauses when the tab becomes hidden (no ticks while hidden)", () => {
    let hidden = false;
    const onTick = vi.fn();
    const poller = createVisibilityPoller({
      intervalMs: 15_000,
      isHidden: () => hidden,
      onTick,
    });
    poller.start();
    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);

    hidden = true;
    poller.handleVisibilityChange();
    expect(poller.isRunning()).toBe(false);

    vi.advanceTimersByTime(60_000);
    expect(onTick).toHaveBeenCalledTimes(1); // nothing fired while hidden
  });

  it("resumes on visibility/focus and ticks again", () => {
    let hidden = false;
    const onTick = vi.fn();
    const poller = createVisibilityPoller({
      intervalMs: 15_000,
      isHidden: () => hidden,
      onTick,
    });
    poller.start();

    hidden = true;
    poller.handleVisibilityChange();
    vi.advanceTimersByTime(45_000);
    expect(onTick).not.toHaveBeenCalled();

    hidden = false;
    poller.handleVisibilityChange(); // visibilitychange / window focus path
    expect(poller.isRunning()).toBe(true);
    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);

    // Resume is idempotent — a second focus event does not double-arm.
    poller.handleVisibilityChange();
    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(2);
  });

  it("start() stays inert while hidden until visibility flips", () => {
    let hidden = true;
    const onTick = vi.fn();
    const poller = createVisibilityPoller({
      intervalMs: 15_000,
      isHidden: () => hidden,
      onTick,
    });

    poller.start();
    expect(poller.isRunning()).toBe(false);
    vi.advanceTimersByTime(30_000);
    expect(onTick).not.toHaveBeenCalled();

    hidden = false;
    poller.handleVisibilityChange();
    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);
  });
});

describe("mockPaperPrice (offline fallback)", () => {
  it("is deterministic per slug/tick, bounded, and drifts between ticks", () => {
    const a1 = mockPaperPrice("nba-2025-01-15-lal-bos", 1);
    const a2 = mockPaperPrice("nba-2025-01-15-lal-bos", 1);
    const a5 = mockPaperPrice("nba-2025-01-15-lal-bos", 5);

    expect(a1).toBe(a2); // deterministic
    expect(a1).toBeGreaterThanOrEqual(0.03);
    expect(a1).toBeLessThanOrEqual(0.97);
    expect(a5).not.toBe(a1); // visible drift → demonstrable live updates
  });
});
