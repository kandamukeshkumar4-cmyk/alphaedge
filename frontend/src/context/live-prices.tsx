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
import { fetchMarketCandles, fetchMarkets } from "@/lib/alphaedge-api";
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

const LivePricesContext = createContext<Record<string, LivePriceState>>({});

const POLL_MS = 1000;
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

function LiveWsBridge({
  slug,
  onTick,
}: {
  slug: string;
  onTick: (slug: string, yes: number, ts: number | null) => void;
}) {
  useEffect(() => {
    if (!slug) return;
    let dead = false;
    let ws: WebSocket | null = null;

    function connect() {
      if (dead) return;
      ws = new WebSocket(`${wsBase()}/api/v1/ws/prices?market=${encodeURIComponent(slug)}`);
      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data) as { yes?: number; ts?: number; keepalive?: boolean };
          if (d.keepalive || typeof d.yes !== "number") return;
          onTick(slug, d.yes, d.ts ?? Date.now() / 1000);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (!dead) setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
    }

    connect();
    return () => {
      dead = true;
      ws?.close();
    };
  }, [slug, onTick]);

  return null;
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

  const onWsTick = useCallback(
    (slug: string, yes: number, ts: number | null) => {
      applyPrice(slug, yes, true, ts);
    },
    [applyPrice],
  );

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

  // Fast catalog poll — one request updates every visible mirror slug.
  useEffect(() => {
    let dead = false;

    const poll = async () => {
      try {
        const fresh = await fetchMarkets();
        if (dead) return;
        ingestMarketPrices(fresh, (slug, price) => {
          applyPrice(slug, price, true, Date.now() / 1000);
        });
      } catch {
        // Whole-catalog fetch failed (backend down) — mark fallbacks as
        // disconnected without a per-slug request fan-out.
        for (const [slug, price] of Object.entries(fallbacksRef.current)) {
          if (dead) return;
          applyPrice(slug, price, false, null);
        }
      }
    };

    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => {
      dead = true;
      clearInterval(id);
    };
  }, [applyPrice]);

  return (
    <>
      {prioritySlugs.map((slug) => (
        <LiveWsBridge key={slug} slug={slug} onTick={onWsTick} />
      ))}
      <LivePricesContext.Provider value={prices}>{children}</LivePricesContext.Provider>
    </>
  );
}

export function useLivePrice(slug: string, fallback: number): LivePriceState {
  const ctx = useContext(LivePricesContext);
  const tick = ctx[slug];
  if (tick && (tick.price > 0 || tick.connected)) return tick;
  return {
    ...EMPTY,
    price: fallback,
    yes: fallback,
    no: Math.round((1 - fallback) * 10000) / 10000,
  };
}

export function useLivePricesMap(): Record<string, LivePriceState> {
  return useContext(LivePricesContext);
}
