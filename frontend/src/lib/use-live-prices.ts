import { useEffect, useState } from "react";

import { fetchLatestPrice } from "./alphaedge-api";
import { wsBase } from "./live-price";

/**
 * Loop 101 — live prices: WebSocket first, 15s REST poll fallback.
 *
 * Opens `/api/v1/ws/prices?market=<slug>` (ws/wss from protocol). On socket
 * error/close, falls back to the existing visibility-aware 15s poller.
 * Polling (and WS reconnect attempts) pause while document.hidden.
 *
 * The pause-on-hidden scheduler and the WS/poll session controller are
 * framework-free so vitest (node environment) can drive them with fake
 * timers and injected sockets.
 */

export const LIVE_PRICES_INTERVAL_MS = 15_000;

export type LivePriceSource = "ws" | "poll";

export type LivePricesState = {
  /** YES-side mid price (0..1), or null before the first update resolves. */
  price: number | null;
  loading: boolean;
  /** ISO timestamp of the last successful refresh. */
  lastUpdated: string | null;
  source: LivePriceSource;
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

/** Minimal WebSocket surface — browser `WebSocket` subset, injectable in tests. */
export type LivePriceSocket = {
  onopen: ((ev?: unknown) => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onerror: ((ev?: unknown) => void) | null;
  onclose: ((ev?: unknown) => void) | null;
  close(): void;
};

export type LivePriceSocketFactory = (url: string) => LivePriceSocket;

/** Build the per-market price WS URL (ws/wss from http/https base or page protocol). */
export function buildPricesWsUrl(slug: string, base?: string): string {
  const resolved = (base ?? wsBase()).replace(/\/$/, "");
  const path = `/api/v1/ws/prices?market=${encodeURIComponent(slug)}`;
  if (resolved) {
    // http(s) → ws(s); already-ws bases pass through.
    const wsRoot = resolved.replace(/^http/, "ws");
    return `${wsRoot}${path}`;
  }
  if (typeof window !== "undefined" && window.location) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${path}`;
  }
  return `ws://localhost:8000${path}`;
}

/** Parse a `/ws/prices` frame into a YES price, or null if not a price tick. */
export function parsePriceWsMessage(raw: string): { price: number; ts: string } | null {
  try {
    const data = JSON.parse(raw) as {
      yes_price?: unknown;
      yes?: unknown;
      ts?: unknown;
      keepalive?: unknown;
    };
    if (data.keepalive) return null;
    const rawPrice = data.yes_price ?? data.yes;
    if (typeof rawPrice !== "number" || !Number.isFinite(rawPrice)) return null;
    let ts: string;
    if (typeof data.ts === "number" && Number.isFinite(data.ts)) {
      ts = new Date(data.ts * 1000).toISOString();
    } else if (typeof data.ts === "string" && data.ts) {
      ts = data.ts;
    } else {
      ts = new Date().toISOString();
    }
    return { price: rawPrice, ts };
  } catch {
    return null;
  }
}

export type LivePriceSession = {
  start(): void;
  stop(): void;
  handleVisibilityChange(): void;
};

export type LivePriceSessionOptions = {
  slug: string;
  intervalMs?: number;
  isHidden: () => boolean;
  onUpdate: (state: LivePricesState) => void;
  /** Injected for tests; defaults to `new WebSocket(url)`. */
  createSocket?: LivePriceSocketFactory;
  /** Injected for tests; defaults to `fetchLatestPrice`. */
  fetchPrice?: (slug: string) => Promise<{ yes: number; ts?: string | null } | null>;
  /** Override WS base (tests). */
  wsUrlBase?: string;
};

/**
 * Framework-free WS-first price session with poll fallback + pause-on-hidden.
 * Used by {@link useLivePrices}; vitest drives it directly with a fake socket.
 */
export function createLivePriceSession(options: LivePriceSessionOptions): LivePriceSession {
  const intervalMs = options.intervalMs ?? LIVE_PRICES_INTERVAL_MS;
  const fetchPrice = options.fetchPrice ?? fetchLatestPrice;
  const createSocket: LivePriceSocketFactory =
    options.createSocket ??
    ((url: string) => new WebSocket(url) as unknown as LivePriceSocket);

  let stopped = false;
  let socket: LivePriceSocket | null = null;
  let usingWs = false;
  let poller: VisibilityPoller | null = null;
  let tick = 0;
  let fallbackArmed = false;

  function emit(partial: Omit<LivePricesState, "loading"> & { loading?: boolean }): void {
    options.onUpdate({
      price: partial.price,
      loading: partial.loading ?? false,
      lastUpdated: partial.lastUpdated,
      source: partial.source,
    });
  }

  async function pollOnce(): Promise<void> {
    if (stopped || options.isHidden()) return;
    tick += 1;
    const live = await fetchPrice(options.slug);
    if (stopped) return;
    if (live && Number.isFinite(live.yes)) {
      emit({
        price: live.yes,
        lastUpdated: live.ts ?? new Date().toISOString(),
        source: "poll",
      });
    } else {
      emit({
        price: mockPaperPrice(options.slug, tick),
        lastUpdated: new Date().toISOString(),
        source: "poll",
      });
    }
  }

  function startPolling(): void {
    if (stopped || poller) return;
    poller = createVisibilityPoller({
      intervalMs,
      isHidden: options.isHidden,
      onTick: () => void pollOnce(),
    });
    void pollOnce();
    poller.start();
  }

  function fallbackToPoll(): void {
    if (stopped || fallbackArmed) return;
    fallbackArmed = true;
    usingWs = false;
    if (socket) {
      const s = socket;
      socket = null;
      try {
        s.close();
      } catch {
        /* ignore */
      }
    }
    startPolling();
  }

  function openSocket(): void {
    if (stopped || options.isHidden()) return;
    const url = buildPricesWsUrl(options.slug, options.wsUrlBase);
    let sock: LivePriceSocket;
    try {
      sock = createSocket(url);
    } catch {
      fallbackToPoll();
      return;
    }
    socket = sock;

    sock.onopen = () => {
      if (stopped || socket !== sock) return;
      usingWs = true;
    };

    sock.onmessage = (ev) => {
      if (stopped || socket !== sock) return;
      const parsed = parsePriceWsMessage(String(ev.data));
      if (!parsed) return;
      usingWs = true;
      emit({
        price: parsed.price,
        lastUpdated: parsed.ts,
        source: "ws",
      });
    };

    sock.onerror = () => {
      if (stopped || socket !== sock) return;
      fallbackToPoll();
    };

    sock.onclose = () => {
      if (stopped || socket !== sock) return;
      socket = null;
      if (usingWs || !fallbackArmed) {
        fallbackToPoll();
      }
    };
  }

  return {
    start(): void {
      stopped = false;
      fallbackArmed = false;
      usingWs = false;
      options.onUpdate({
        price: null,
        loading: true,
        lastUpdated: null,
        source: "poll",
      });
      if (options.isHidden()) return;
      openSocket();
    },
    stop(): void {
      stopped = true;
      poller?.stop();
      poller = null;
      if (socket) {
        const s = socket;
        socket = null;
        try {
          s.close();
        } catch {
          /* ignore */
        }
      }
    },
    handleVisibilityChange(): void {
      if (stopped) return;
      if (options.isHidden()) {
        poller?.handleVisibilityChange();
        if (socket) {
          const s = socket;
          socket = null;
          try {
            s.close();
          } catch {
            /* ignore */
          }
        }
        return;
      }
      // Visible again: prefer WS if we never fell back; else keep polling.
      if (fallbackArmed) {
        poller?.handleVisibilityChange();
      } else if (!socket) {
        openSocket();
      }
    },
  };
}

/**
 * Live price for `slug`: WebSocket first, 15s poll fallback, pause while hidden.
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
    source: "poll",
  });

  useEffect(() => {
    const session = createLivePriceSession({
      slug,
      intervalMs,
      isHidden: () => typeof document !== "undefined" && document.hidden,
      onUpdate: (next) => setState(next),
    });
    session.start();

    const onVisibility = () => session.handleVisibilityChange();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onVisibility);
    return () => {
      session.stop();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onVisibility);
    };
  }, [slug, intervalMs]);

  return state;
}
