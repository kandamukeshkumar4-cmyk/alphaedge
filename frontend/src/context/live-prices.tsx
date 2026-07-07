"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { fetchLatestPrice, fetchMarketCandles } from "@/lib/alphaedge-api";
import { isLiveMirror } from "@/lib/hero-market";
import { resolveOutcomeSlug, wsBase } from "@/lib/live-price";
import type { Market } from "@/lib/mock-data";

export type LivePriceState = {
  price: number;
  yes: number;
  no: number;
  flash: "up" | "down" | null;
  connected: boolean;
  /** Percentage-point move vs session / candle baseline. */
  deltaPts: number;
  ts: number | null;
};

const EMPTY: LivePriceState = {
  price: 0,
  yes: 0,
  no: 0,
  flash: null,
  connected: false,
  deltaPts: 0,
  ts: null,
};

type LivePricesContextValue = {
  prices: Record<string, LivePriceState>;
  /** Subscribe a card to a slug; returns an unsubscribe. The provider's single
   * poll loop fetches only the union of `prioritySlugs` and subscribed slugs. */
  subscribe: (slug: string) => () => void;
};

const LivePricesContext = createContext<LivePricesContextValue>({
  prices: {},
  subscribe: () => () => {},
});

// Plan 007: catalog poll was 1s and fetched the FULL catalog. Now a single
// lightweight poll loop fetches only subscribed/priority slugs at 5s.
const POLL_MS = 5000;
const FLASH_MS = 600;

function ingestMarketPrices(markets: Market[], apply: (slug: string, price: number) => void) {
  for (const m of markets) {
    if (!isLiveMirror(m)) continue;
    for (const o of m.outcomes) {
      const slug = resolveOutcomeSlug(o.id, m.slug);
      // Binary markets: only ingest YES — NO shares the same slug and would overwrite.
      if (o.id === "no" && slug === m.slug) continue;
      apply(slug, o.price);
    }
  }
}

/**
 * Refcounted subscription registry. Multiple cards subscribing to the same slug
 * produce ONE slot (refcount), so the provider runs a single poll loop with one
 * fetch per slug regardless of subscriber count — no per-card WebSocket/poll.
 */
export class SubscriptionRegistry {
  private counts = new Map<string, number>();

  subscribe(slug: string): () => void {
    if (!slug) return () => {};
    this.counts.set(slug, (this.counts.get(slug) ?? 0) + 1);
    return () => this.unsubscribe(slug);
  }

  unsubscribe(slug: string): void {
    const n = this.counts.get(slug);
    if (n === undefined) return;
    if (n <= 1) this.counts.delete(slug);
    else this.counts.set(slug, n - 1);
  }

  has(slug: string): boolean {
    return this.counts.has(slug);
  }

  size(): number {
    return this.counts.size;
  }

  slugs(): string[] {
    return [...this.counts.keys()];
  }
}

/** Dedup priority + dynamically subscribed slugs into the single poll list. */
export function selectPollSlugs(priority: string[], subscribed: string[]): string[] {
  const set = new Set<string>();
  for (const s of priority) if (s) set.add(s);
  for (const s of subscribed) if (s) set.add(s);
  return [...set];
}

/** Minimal WebSocket surface the multiplexer relies on — lets tests inject a
 *  fake socket without a real network. Matches the browser `WebSocket` subset. */
export type FeedSocket = {
  onopen: (() => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  close: () => void;
};

export type FeedTick = { slug: string; yes: number; ts: number | null };

/**
 * Parse one raw `/api/v1/ws/feed` frame into a price tick — but ONLY when it is
 * a `market.tick` frame (Loop 2 routed ticks through the event bus onto the
 * multiplexed feed socket) for a slug that is currently active. Every other
 * channel (briefs/alerts/system) and every inactive slug is filtered out.
 * Returns null when the frame is not an applicable tick.
 */
export function selectFeedTick(
  raw: unknown,
  isActive: (slug: string) => boolean,
): FeedTick | null {
  if (!raw || typeof raw !== "object") return null;
  const f = raw as { channel?: unknown; slug?: unknown; yes?: unknown; ts?: unknown };
  if (f.channel !== "market.tick") return null;
  if (typeof f.slug !== "string" || !isActive(f.slug)) return null;
  if (typeof f.yes !== "number") return null;
  return { slug: f.slug, yes: f.yes, ts: typeof f.ts === "number" ? f.ts : null };
}

/**
 * ONE shared WebSocket to `/api/v1/ws/feed`, multiplexing live prices for every
 * subscribed card. Plan 007: replaces the old up-to-24 per-card sockets. The
 * provider owns a single FeedMultiplexer for its lifetime; incoming `market.tick`
 * frames are filtered per-slug against the active subscription set and dispatched
 * to `onTick`. Auto-reconnects with capped exponential backoff. `connectionCount`
 * proves (in tests) that N subscribers still share exactly one live connection.
 */
export class FeedMultiplexer {
  private socket: FeedSocket | null = null;
  private dead = false;
  private retry = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private opens = 0;

  constructor(
    private readonly createSocket: () => FeedSocket | null,
    private readonly onTick: (tick: FeedTick) => void,
    private readonly isActive: (slug: string) => boolean,
  ) {}

  /** Total sockets opened over this multiplexer's life (1 + reconnects). */
  get connectionCount(): number {
    return this.opens;
  }

  start(): void {
    if (this.dead || this.socket) return;
    const sock = this.createSocket();
    if (!sock) return;
    this.opens += 1;
    this.socket = sock;
    sock.onopen = () => {
      this.retry = 0;
    };
    sock.onmessage = (ev) => {
      let raw: unknown;
      try {
        raw = JSON.parse(ev.data);
      } catch {
        return;
      }
      const tick = selectFeedTick(raw, this.isActive);
      if (tick) this.onTick(tick);
    };
    sock.onclose = () => {
      this.socket = null;
      if (this.dead) return;
      const delay = Math.min(30_000, 1_000 * 2 ** this.retry);
      this.retry += 1;
      this.timer = setTimeout(() => this.start(), delay);
    };
    sock.onerror = () => sock.close();
  }

  stop(): void {
    this.dead = true;
    if (this.timer) clearTimeout(this.timer);
    this.socket?.close();
    this.socket = null;
  }
}

export function collectLiveSlugs(markets: Market[]): string[] {
  const slugs = new Set<string>();
  for (const m of markets) {
    if (!isLiveMirror(m)) continue;
    slugs.add(m.slug);
    for (const o of m.outcomes) {
      slugs.add(resolveOutcomeSlug(o.id, m.slug));
    }
  }
  return [...slugs];
}

export function collectPrioritySlugs(
  heroMarkets: Market[],
  extraMarkets: Market[] = [],
  maxSlugs = 24,
): string[] {
  const slugs = new Set<string>();
  for (const m of [...heroMarkets, ...extraMarkets]) {
    if (!isLiveMirror(m)) continue;
    for (const o of m.outcomes.slice(0, 4)) {
      slugs.add(resolveOutcomeSlug(o.id, m.slug));
      if (slugs.size >= maxSlugs) return [...slugs];
    }
  }
  return [...slugs];
}

export function LivePricesProvider({
  markets,
  prioritySlugs = [],
  children,
}: {
  markets: Market[];
  prioritySlugs?: string[];
  children: ReactNode;
}) {
  const [prices, setPrices] = useState<Record<string, LivePriceState>>({});
  const baselines = useRef<Record<string, number>>({});
  const prevPrices = useRef<Record<string, number>>({});
  const flashTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const baselineLoaded = useRef<Set<string>>(new Set());

  // One subscription registry for the whole provider lifetime. Cards register
  // their slug via `subscribe`; the single poll loop reads this ref each tick.
  const registryRef = useRef<SubscriptionRegistry | null>(null);
  if (registryRef.current === null) registryRef.current = new SubscriptionRegistry();
  // Ref mirror of prioritySlugs so the poll effect can depend on a stable
  // callback and never re-arm — exactly one interval for the provider lifetime.
  const prioritySlugsRef = useRef<string[]>(prioritySlugs);
  useEffect(() => {
    prioritySlugsRef.current = prioritySlugs;
  }, [prioritySlugs]);

  const fallbacks = useMemo(() => {
    const map: Record<string, number> = {};
    ingestMarketPrices(markets, (slug, price) => {
      map[slug] = price;
    });
    return map;
  }, [markets]);
  // Ref so the poll effect never re-arms when a parent rebuilds the markets
  // array each render — that identity churn caused a fetch-per-render storm.
  const fallbacksRef = useRef(fallbacks);
  useEffect(() => {
    fallbacksRef.current = fallbacks;
  }, [fallbacks]);

  const applyPrice = useCallback((slug: string, yes: number, connected: boolean, ts: number | null) => {
    if (!slug || yes < 0) return;

    setPrices((prev) => {
      const prior = prevPrices.current[slug];
      let flash: "up" | "down" | null = null;
      if (prior !== undefined && yes !== prior) {
        flash = yes > prior ? "up" : "down";
        const existing = flashTimers.current[slug];
        if (existing) clearTimeout(existing);
        flashTimers.current[slug] = setTimeout(() => {
          setPrices((p) => {
            const row = p[slug];
            if (!row || row.flash === null) return p;
            return { ...p, [slug]: { ...row, flash: null } };
          });
        }, FLASH_MS);
      }
      prevPrices.current[slug] = yes;

      if (!(slug in baselines.current)) {
        baselines.current[slug] = yes;
      }
      const baseline = baselines.current[slug];
      const deltaPts = Math.round((yes - baseline) * 100);
      const no = Math.round((1 - yes) * 10000) / 10000;

      const existing = prev[slug];
      if (
        existing &&
        existing.price === yes &&
        existing.flash === flash &&
        existing.connected === connected &&
        existing.deltaPts === deltaPts
      ) {
        return prev;
      }

      return {
        ...prev,
        [slug]: { price: yes, yes, no, flash, connected, deltaPts, ts },
      };
    });
  }, []);

  // Candle baseline = trend vs start of visible history (real market move).
  useEffect(() => {
    for (const slug of prioritySlugs) {
      if (baselineLoaded.current.has(slug)) continue;
      baselineLoaded.current.add(slug);
      void fetchMarketCandles(slug, 36).then((candles) => {
        const first = candles?.[0]?.close;
        if (typeof first === "number") {
          baselines.current[slug] = first;
          const current = prevPrices.current[slug] ?? fallbacks[slug];
          if (typeof current === "number") {
            applyPrice(slug, current, true, null);
          }
        }
      });
    }
  }, [prioritySlugs, fallbacks, applyPrice]);

  useEffect(() => {
    const timersRef = flashTimers;
    return () => {
      for (const t of Object.values(timersRef.current)) clearTimeout(t);
    };
  }, []);

  // Single shared poll loop (Plan 007). Replaces the old 1s full-catalog poll
  // AND the per-card WebSockets. Fetches ONLY the union of priority + subscribed
  // slugs, one `fetchLatestPrice` per slug, deduped. Falls back to mock-derived
  // prices (disconnected) per slug when the API is down — mock data preserved.
  useEffect(() => {
    let dead = false;

    const poll = async () => {
      if (dead) return;
      const reg = registryRef.current;
      const slugs = selectPollSlugs(prioritySlugsRef.current, reg?.slugs() ?? []);
      await Promise.all(
        slugs.map(async (slug) => {
          const live = await fetchLatestPrice(slug);
          if (dead) return;
          if (live && typeof live.yes === "number") {
            applyPrice(slug, live.yes, true, Date.now() / 1000);
          } else {
            // API down / no row for this slug — keep mock fallback, mark offline.
            const fb = fallbacksRef.current[slug];
            if (typeof fb === "number") applyPrice(slug, fb, false, null);
          }
        }),
      );
    };

    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => {
      dead = true;
      clearInterval(id);
    };
  }, [applyPrice]);

  // Single multiplexed WS (Plan 007). One `/api/v1/ws/feed` connection carries
  // every card's live price via `market.tick` frames; cards "subscribe" only by
  // registering their slug in the registry above. A frame is applied iff its
  // slug is a priority or subscribed slug. The 5s poll remains as fallback for
  // slugs that haven't ticked yet / when the socket is down. Degrades silently
  // when no backend WS base is configured (static export) — poll-only then.
  useEffect(() => {
    if (!wsBase()) return;
    const isActive = (slug: string) =>
      prioritySlugsRef.current.includes(slug) || (registryRef.current?.has(slug) ?? false);
    const mux = new FeedMultiplexer(
      () =>
        typeof WebSocket === "undefined"
          ? null
          : (new WebSocket(`${wsBase()}/api/v1/ws/feed`) as unknown as FeedSocket),
      (tick) => applyPrice(tick.slug, tick.yes, true, tick.ts),
      isActive,
    );
    mux.start();
    return () => mux.stop();
  }, [applyPrice]);

  const subscribe = useCallback((slug: string) => {
    const reg = registryRef.current;
    if (!reg) return () => {};
    return reg.subscribe(slug);
  }, []);

  const ctx = useMemo<LivePricesContextValue>(
    () => ({ prices, subscribe }),
    [prices, subscribe],
  );

  return <LivePricesContext.Provider value={ctx}>{children}</LivePricesContext.Provider>;
}

export function useLivePrice(slug: string, fallback: number): LivePriceState {
  const { prices, subscribe } = useContext(LivePricesContext);
  useEffect(() => {
    const unsub = subscribe(slug);
    return unsub;
  }, [slug, subscribe]);
  const tick = prices[slug];
  if (tick && (tick.price > 0 || tick.connected)) return tick;
  return {
    ...EMPTY,
    price: fallback,
    yes: fallback,
    no: Math.round((1 - fallback) * 10000) / 10000,
  };
}

export function useLivePricesMap(): Record<string, LivePriceState> {
  return useContext(LivePricesContext).prices;
}
