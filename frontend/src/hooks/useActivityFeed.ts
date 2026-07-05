"use client";

import { useEffect, useRef } from "react";
import { wsBase } from "@/lib/live-price";
import { API_BASE } from "@/lib/alphaedge-api";

export type BriefFrame = {
  channel: "briefs";
  market_slug?: string;
  headline?: string;
  direction?: string;
  generator?: string;
  ts?: number;
};

export type AlertFrame = {
  channel: "alerts";
  type?: string;
  message?: string;
  [k: string]: unknown;
};

type Handlers = {
  onBrief?: (frame: BriefFrame) => void;
  onAlert?: (frame: AlertFrame) => void;
};

// Subscribes to the multiplexed `/api/v1/ws/feed` socket and dispatches live
// analyst briefs + dispatched alerts to the given handlers. Auto-reconnects
// with backoff. Handlers are held in a ref so re-renders don't re-open the
// socket. Consumers still do an initial REST fetch for backfill; this streams
// everything that happens after connect, replacing 30s re-polling.
export function useActivityFeed(handlers: Handlers): void {
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    // No backend configured (demo/static deploy) → don't open a socket that
    // can never connect and would reconnect forever. REST clients guard the
    // same way on empty API_BASE.
    if (!API_BASE) return;

    let dead = false;
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (dead) return;
      ws = new WebSocket(`${wsBase()}/api/v1/ws/feed`);

      ws.onopen = () => {
        retry = 0;
      };
      ws.onmessage = (ev) => {
        try {
          const frame = JSON.parse(ev.data) as { channel?: string };
          if (frame.channel === "briefs") {
            handlersRef.current.onBrief?.(frame as BriefFrame);
          } else if (frame.channel === "alerts") {
            handlersRef.current.onAlert?.(frame as AlertFrame);
          }
          // channel === "system" (connected/keepalive) is ignored.
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onclose = () => {
        if (dead) return;
        const delay = Math.min(30_000, 1_000 * 2 ** retry);
        retry += 1;
        timer = setTimeout(connect, delay);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      dead = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, []);
}
