"use client";

import { useEffect, useRef, useState } from "react";

import { WS_BASE } from "@/lib/alphaedge-api";

export function useMarketPrice(slug: string): {
  yes: number;
  no: number;
  loading: boolean;
} {
  const [yes, setYes] = useState(0);
  const [no, setNo] = useState(0);
  const [loading, setLoading] = useState(true);
  const reconnectAttempted = useRef(false);

  useEffect(() => {
    if (!WS_BASE || !slug) {
      setLoading(true);
      return;
    }

    let ws: WebSocket | null = null;
    let cancelled = false;

    const connect = () => {
      ws = new WebSocket(
        `${WS_BASE}/api/v1/ws/prices?market=${encodeURIComponent(slug)}`,
      );

      ws.onopen = () => {
        if (!cancelled) {
          setLoading(false);
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as {
            yes?: number;
            no?: number;
          };
          if (
            !cancelled &&
            typeof data.yes === "number" &&
            typeof data.no === "number"
          ) {
            setYes(data.yes);
            setNo(data.no);
            setLoading(false);
          }
        } catch {
          // ignore malformed payloads
        }
      };

      ws.onclose = () => {
        if (cancelled) {
          return;
        }
        if (!reconnectAttempted.current) {
          reconnectAttempted.current = true;
          connect();
          return;
        }
        setLoading(true);
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    reconnectAttempted.current = false;
    setLoading(true);
    connect();

    return () => {
      cancelled = true;
      ws?.close();
    };
  }, [slug]);

  return { yes, no, loading };
}
