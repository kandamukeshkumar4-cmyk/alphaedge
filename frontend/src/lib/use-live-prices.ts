import { useEffect, useRef, useState } from "react";

import { fetchLatestPrice } from "./alphaedge-api";

/**
 * Loop V90 (C3) — live prices polling hook (v1: REST polling, NOT websocket).
 *
 * Refetches a market's price (GET /api/v1/markets/{slug}/prices/latest) every
 * 15s. Polling PAUSES while document.hidden (no background-tab waste) and
 * resumes on visibilitychange / window focus. Live-first with a deterministic
 * PAPER mock fallback so the price surface keeps updating with no backend.
 *
 * The pause-on-hidden scheduler is factored out as {@link createVisibilityPoller}
 * — framework-free so vitest (node environment) can drive it with fake timers
 * and a mocked visibility flag.
 */

export const LIVE_PRICES_INTERVAL_MS = 15_000;

export type LivePricesState = {
  /** YES-side mid price (0..1), or null before the first fetch resolves. */
  price: number | null;
  loading: boolean;
  /** ISO timestamp of the last successful refresh (live ts or mock time). */
  lastUpdated: string | null;
  source: "live" | "mock";
};

export type VisibilityPoller = {
  /** Begin polling (no-op while hidden — the visibility handler arms it). */
  start(): void;
  /** Permanently stop polling. */
  stop(): void;
  /** Re-evaluate visibility: pause when hidden, resume when visible. */
  handleVisibilityChange(): void;
  isRunning(): boolean;
};

export type VisibilityPollerOptions = {
  intervalMs: number;
  /** Visibility predicate — `() => document.hidden` in the browser. */
  isHidden: () => boolean;
  onTick: () => void;
};

/**
 * Interval poller that suspends itself while its visibility predicate reports
 * hidden. Pure scheduling — no DOM, no React — so tests mock visibility by
 * passing their own `isHidden`.
 */
export function createVisibilityPoller(options: VisibilityPollerOptions): VisibilityPoller {
  let timer: ReturnType<typeof setInterval> | null = null;

  function pause(): void {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }

  function resume(): void {
    if (timer !== null) return;
    timer = setInterval(() => {
      if (!options.isHidden()) options.onTick();
    }, options.intervalMs);
  }

  return {
    start(): void {
      if (!options.isHidden()) resume();
    },
    stop(): void {
      pause();
    },
    handleVisibilityChange(): void {
      if (options.isHidden()) pause();
      else resume();
    },
    isRunning(): boolean {
      return timer !== null;
    },
  };
}

/**
 * Deterministic PAPER mock price: stable base per slug + a gentle sine drift
 * per tick, so the chip visibly moves between polls with no backend.
 * Simulated funds only — research display, never an execution price.
 */
export function mockPaperPrice(slug: string, tick: number): number {
  let hash = 0;
  for (let i = 0; i < slug.length; i += 1) {
    hash = (hash * 31 + slug.charCodeAt(i)) % 100_000;
  }
  const base = 0.35 + (hash % 30) / 100; // 0.35–0.64 per slug
  const drift = Math.sin(tick / 3) * 0.02;
  return Number(Math.min(0.97, Math.max(0.03, base + drift)).toFixed(3));
}

/**
 * Poll `slug`'s price every `intervalMs` (default 15s), pausing while the tab
 * is hidden and resuming on visibility/focus. Never throws; falls back to the
 * deterministic mock price when the API is absent so live updates remain
 * demonstrable offline.
 */
export function useLivePrices(
  slug: string,
  options?: { intervalMs?: number },
): LivePricesState {
  const intervalMs = options?.intervalMs ?? LIVE_PRICES_INTERVAL_MS;
  const [state, setState] = useState<LivePricesState>({
    price: null,
    loading: true,
    lastUpdated: null,
    source: "mock",
  });
  const tickRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    tickRef.current = 0;
    setState({ price: null, loading: true, lastUpdated: null, source: "mock" });

    async function poll(): Promise<void> {
      tickRef.current += 1;
      const tick = tickRef.current;
      const live = await fetchLatestPrice(slug);
      if (cancelled) return;
      if (live && Number.isFinite(live.yes)) {
        setState({
          price: live.yes,
          loading: false,
          lastUpdated: live.ts ?? new Date().toISOString(),
          source: "live",
        });
      } else {
        setState({
          price: mockPaperPrice(slug, tick),
          loading: false,
          lastUpdated: new Date().toISOString(),
          source: "mock",
        });
      }
    }

    void poll();
    const poller = createVisibilityPoller({
      intervalMs,
      isHidden: () => typeof document !== "undefined" && document.hidden,
      onTick: () => void poll(),
    });
    poller.start();

    const onVisibility = () => poller.handleVisibilityChange();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onVisibility);
    return () => {
      cancelled = true;
      poller.stop();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onVisibility);
    };
  }, [slug, intervalMs]);

  return state;
}
