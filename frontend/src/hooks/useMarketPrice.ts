"use client";
import { useEffect, useRef, useState } from "react";

export interface MarketPrice {
  /** Live YES price, or null when no valid tick has arrived. Never NaN. */
  yes: number | null;
  /** Live NO price (1 - yes), or null. Never NaN. */
  no: number | null;
  ts: number | null;
  connected: boolean;
}

const RECONNECT_DELAY_MS = 3000;

/**
 * Loop117 (D1b/D19): the `/api/v1/ws/prices` frame is
 * `{slug, yes_price, ts}` — this hook used to read `d.yes` / `d.no`, which are
 * not in the frame. Every tick therefore set `{yes: undefined, connected: true}`,
 * and PriceChart's live-tick effect wrote `Math.max(high, undefined)` = NaN into
 * lightweight-charts. In dev that assertion throws inside a React effect and
 * unmounts the whole market page (the Paper buy button detaches mid-click, the
 * chart region never appears); in prod the assertion is stripped, so the header
 * renders `NaN¢ ▼ NaN¢ (NaN%)`.
 *
 * The frame is parsed here, once: only a finite 0..1 number is ever published,
 * and "no price yet" is an honest `null` that callers render as a dash.
 */
export function parsePriceFrame(
  raw: unknown,
): { yes: number; no: number; ts: number } | null {
  if (!raw || typeof raw !== "object") return null;
  const frame = raw as Record<string, unknown>;
  if (frame.keepalive) return null;
  // `yes_price` is the wire field; `yes` is accepted for any legacy publisher.
  const value = frame.yes_price ?? frame.yes;
  const yes = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(yes) || yes < 0 || yes > 1) return null;
  const rawTs = Number(frame.ts);
  return {
    yes,
    no: Math.round((1 - yes) * 10000) / 10000,
    ts: Number.isFinite(rawTs) ? rawTs : Math.floor(Date.now() / 1000),
  };
}

/** Usable live YES price, or null — callers fall back to the stored price. */
export function liveYes(state: MarketPrice): number | null {
  return state.connected && state.yes !== null && state.yes > 0 ? state.yes : null;
}

/** Usable live NO price, or null. */
export function liveNo(state: MarketPrice): number | null {
  return state.connected && state.no !== null && state.no > 0 ? state.no : null;
}

const DISCONNECTED: MarketPrice = {
  yes: null,
  no: null,
  ts: null,
  connected: false,
};

export function useMarketPrice(slug: string, enabled = true): MarketPrice {
  const [state, setState] = useState<MarketPrice>(DISCONNECTED);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!slug || !enabled) {
      setState(DISCONNECTED);
      return;
    }
    let dead = false;

    function connect() {
      if (dead) return;
      const base =
        process.env.NEXT_PUBLIC_WS_URL?.replace(/^http/, "ws") ??
        "ws://localhost:8000";
      const ws = new WebSocket(`${base}/api/v1/ws/prices?market=${slug}`);
      wsRef.current = ws;

      // `connected` stays false until a usable price arrives: consumers gate
      // their live-price branch on it, and an open socket with no tick is not
      // a price.
      ws.onmessage = (ev) => {
        try {
          const tick = parsePriceFrame(JSON.parse(ev.data));
          if (!tick) return;
          setState({ ...tick, connected: true });
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = () => {
        setState(DISCONNECTED);
        if (!dead) setTimeout(connect, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      dead = true;
      wsRef.current?.close();
    };
  }, [slug, enabled]);

  return state;
}
