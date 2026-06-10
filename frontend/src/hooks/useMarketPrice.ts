"use client";
import { useEffect, useRef, useState } from "react";

interface MarketPrice {
  yes: number;
  no: number;
  ts: number | null;
  connected: boolean;
}

const RECONNECT_DELAY_MS = 3000;

export function useMarketPrice(slug: string): MarketPrice {
  const [state, setState] = useState<MarketPrice>({
    yes: 0,
    no: 0,
    ts: null,
    connected: false,
  });
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!slug) return;
    let dead = false;

    function connect() {
      if (dead) return;
      const base =
        process.env.NEXT_PUBLIC_WS_URL?.replace(/^http/, "ws") ??
        "ws://localhost:8000";
      const ws = new WebSocket(`${base}/api/v1/ws/prices?market=${slug}`);
      wsRef.current = ws;

      ws.onopen = () => setState((s) => ({ ...s, connected: true }));

      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);
          if (d.keepalive) return;
          setState({ yes: d.yes, no: d.no, ts: d.ts, connected: true });
        } catch {
          /* ignore malformed frames */
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
      wsRef.current?.close();
    };
  }, [slug]);

  return state;
}
