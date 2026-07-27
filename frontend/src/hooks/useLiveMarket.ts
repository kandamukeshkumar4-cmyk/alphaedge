"use client";

import { useEffect, useRef, useState } from "react";
import { fetchLatestPrice } from "@/lib/alphaedge-api";
import { wsBase } from "@/lib/live-price";

export type LiveMarketTick = {
  yes: number;
  no: number;
  ts: number | null;
  connected: boolean;
  flash: "up" | "down" | null;
};

const RECONNECT_DELAY_MS = 2000;
const POLL_MS = 1000;

/** WebSocket ticks plus fast HTTP poll so the hero feels live like Kalshi. */
export function useLiveMarket(slug: string, enabled = true): LiveMarketTick {
  const [state, setState] = useState<LiveMarketTick>({
    yes: 0,
    no: 0,
    ts: null,
    connected: false,
    flash: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const prevYes = useRef<number | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!slug || !enabled) return;
    prevYes.current = null;
    let dead = false;

    const applyTick = (yes: number, ts: number | null, connected: boolean) => {
      const no = Math.round((1 - yes) * 10000) / 10000;
      let flash: "up" | "down" | null = null;
      if (prevYes.current !== null && yes !== prevYes.current) {
        flash = yes > prevYes.current ? "up" : "down";
        if (flashTimer.current) clearTimeout(flashTimer.current);
        flashTimer.current = setTimeout(() => {
          setState((s) => ({ ...s, flash: null }));
        }, 500);
      }
      prevYes.current = yes;
      setState({ yes, no, ts, connected, flash });
    };

    const poll = async () => {
      const latest = await fetchLatestPrice(slug);
      if (dead || !latest) return;
      applyTick(latest.yes, latest.ts ? Date.parse(latest.ts) / 1000 : Date.now() / 1000, true);
    };

    void poll();
    const pollId = setInterval(() => void poll(), POLL_MS);

    function connect() {
      if (dead) return;
      const ws = new WebSocket(`${wsBase()}/api/v1/ws/prices?market=${encodeURIComponent(slug)}`);
      wsRef.current = ws;

      ws.onopen = () => setState((s) => ({ ...s, connected: true }));

      ws.onmessage = (ev) => {
        try {
          // The `/api/v1/ws/prices` frame is `{slug, yes_price, ts}` — this
          // handler used to read `d.yes`, which the guard then rejected, so
          // every tick was silently dropped. Mirrors parsePriceFrame in
          // useMarketPrice.ts: only a finite 0..1 number is ever applied;
          // anything else is dropped (published as "no new tick").
          const d = JSON.parse(ev.data) as {
            yes_price?: unknown;
            yes?: unknown;
            ts?: unknown;
            keepalive?: boolean;
          };
          if (d.keepalive) return;
          // `yes_price` is the wire field; `yes` is accepted for any legacy publisher.
          const value = d.yes_price ?? d.yes;
          const yes = typeof value === "number" ? value : Number(value);
          if (!Number.isFinite(yes) || yes < 0 || yes > 1) return;
          const ts = Number(d.ts);
          applyTick(yes, Number.isFinite(ts) ? ts : Date.now() / 1000, true);
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!dead) setTimeout(connect, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      dead = true;
      clearInterval(pollId);
      if (flashTimer.current) clearTimeout(flashTimer.current);
      wsRef.current?.close();
    };
  }, [slug, enabled]);

  return state;
}
