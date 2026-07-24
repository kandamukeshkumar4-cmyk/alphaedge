import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildPricesWsUrl,
  createLivePriceSession,
  createVisibilityPoller,
  mockPaperPrice,
  parsePriceWsMessage,
  type LivePriceSocket,
  type LivePricesState,
} from "./use-live-prices";

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

describe("buildPricesWsUrl / parsePriceWsMessage", () => {
  it("maps https base to wss and encodes the market slug", () => {
    expect(buildPricesWsUrl("nba-2025-01-15-lal-bos", "https://api.example.com")).toBe(
      "wss://api.example.com/api/v1/ws/prices?market=nba-2025-01-15-lal-bos",
    );
    expect(buildPricesWsUrl("a b", "http://localhost:8000")).toBe(
      "ws://localhost:8000/api/v1/ws/prices?market=a%20b",
    );
  });

  it("parses yes_price ticks and ignores keepalives", () => {
    expect(parsePriceWsMessage(JSON.stringify({ keepalive: true }))).toBeNull();
    const parsed = parsePriceWsMessage(
      JSON.stringify({ slug: "nba-2025-01-15-lal-bos", yes_price: 0.61, ts: 1_700_000_000 }),
    );
    expect(parsed?.price).toBe(0.61);
    expect(parsed?.ts).toBe(new Date(1_700_000_000 * 1000).toISOString());
  });
});

/** In-memory fake of the browser WebSocket subset the session uses. */
class FakeSocket implements LivePriceSocket {
  onopen: ((ev?: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev?: unknown) => void) | null = null;
  onclose: ((ev?: unknown) => void) | null = null;
  closed = false;

  close(): void {
    this.closed = true;
    this.onclose?.({});
  }

  emit(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

describe("createLivePriceSession (WS-first + poll fallback)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("updates price from a WS message with source ws", () => {
    let hidden = false;
    const updates: LivePricesState[] = [];
    let sock: FakeSocket | null = null;

    const session = createLivePriceSession({
      slug: "nba-2025-01-15-lal-bos",
      intervalMs: 15_000,
      isHidden: () => hidden,
      wsUrlBase: "ws://test",
      createSocket: () => {
        sock = new FakeSocket();
        return sock;
      },
      fetchPrice: vi.fn(async () => ({ yes: 0.4, ts: "2026-01-01T00:00:00.000Z" })),
      onUpdate: (s) => updates.push({ ...s }),
    });

    session.start();
    expect(sock).not.toBeNull();
    sock!.onopen?.({});
    sock!.emit({ slug: "nba-2025-01-15-lal-bos", yes_price: 0.62, ts: 1_700_000_000 });

    const last = updates.at(-1)!;
    expect(last.source).toBe("ws");
    expect(last.price).toBe(0.62);
    expect(last.loading).toBe(false);
    expect(last.lastUpdated).toBe(new Date(1_700_000_000 * 1000).toISOString());
    session.stop();
  });

  it("falls back to poll on WS error", async () => {
    let hidden = false;
    const updates: LivePricesState[] = [];
    let sock: FakeSocket | null = null;
    const fetchPrice = vi.fn(async () => ({
      yes: 0.55,
      ts: "2026-07-24T12:00:00.000Z",
    }));

    const session = createLivePriceSession({
      slug: "nba-2025-01-15-lal-bos",
      intervalMs: 15_000,
      isHidden: () => hidden,
      wsUrlBase: "ws://test",
      createSocket: () => {
        sock = new FakeSocket();
        return sock;
      },
      fetchPrice,
      onUpdate: (s) => updates.push({ ...s }),
    });

    session.start();
    sock!.onerror?.({});

    // pollOnce is async — flush microtasks
    await vi.advanceTimersByTimeAsync(0);

    expect(fetchPrice).toHaveBeenCalled();
    const polled = updates.find((u) => u.source === "poll" && u.price === 0.55);
    expect(polled).toBeDefined();
    expect(polled!.lastUpdated).toBe("2026-07-24T12:00:00.000Z");
    session.stop();
  });

  it("pauses polling while hidden after WS fallback", async () => {
    let hidden = false;
    const updates: LivePricesState[] = [];
    let sock: FakeSocket | null = null;
    const fetchPrice = vi.fn(async () => ({
      yes: 0.5,
      ts: "2026-07-24T12:00:00.000Z",
    }));

    const session = createLivePriceSession({
      slug: "nba-2025-01-15-lal-bos",
      intervalMs: 15_000,
      isHidden: () => hidden,
      wsUrlBase: "ws://test",
      createSocket: () => {
        sock = new FakeSocket();
        return sock;
      },
      fetchPrice,
      onUpdate: (s) => updates.push({ ...s }),
    });

    session.start();
    sock!.onerror?.({});
    await vi.advanceTimersByTimeAsync(0);
    const callsAfterFallback = fetchPrice.mock.calls.length;
    expect(callsAfterFallback).toBeGreaterThanOrEqual(1);

    hidden = true;
    session.handleVisibilityChange();

    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchPrice.mock.calls.length).toBe(callsAfterFallback);

    hidden = false;
    session.handleVisibilityChange();
    await vi.advanceTimersByTimeAsync(15_000);
    expect(fetchPrice.mock.calls.length).toBeGreaterThan(callsAfterFallback);
    session.stop();
  });
});
