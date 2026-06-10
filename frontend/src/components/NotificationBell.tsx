"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

interface PriceAlert {
  slug: string;
  yes: number;
  no: number;
  ts: number;
  id: string;
  read: boolean;
}

function useGlobalPriceAlerts(slugs: string[]): {
  alerts: PriceAlert[];
  unread: number;
  markAllRead: () => void;
} {
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const wsRefs = useRef<Map<string, WebSocket>>(new Map());

  useEffect(() => {
    if (typeof window === "undefined") return;

    const base =
      process.env.NEXT_PUBLIC_WS_URL?.replace(/^http/, "ws") ?? "ws://localhost:8000";

    function connect(slug: string) {
      const ws = new WebSocket(`${base}/api/v1/ws/prices?market=${slug}`);
      wsRefs.current.set(slug, ws);

      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data) as {
            slug: string;
            yes: number;
            no: number;
            ts: number;
            alert?: boolean;
            keepalive?: boolean;
          };
          if (!d.alert) return;
          const alert: PriceAlert = {
            slug: d.slug,
            yes: d.yes,
            no: d.no,
            ts: d.ts,
            id: `${d.slug}-${d.ts}`,
            read: false,
          };
          setAlerts((prev) => {
            if (prev.some((a) => a.id === alert.id)) return prev;
            return [alert, ...prev].slice(0, 50);
          });
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        if (!wsRefs.current.has(slug)) return;
        setTimeout(() => {
          if (wsRefs.current.has(slug)) connect(slug);
        }, 5000);
      };

      ws.onerror = () => ws.close();
    }

    for (const slug of slugs) {
      connect(slug);
    }

    const currentRefs = wsRefs.current;
    return () => {
      for (const [slug, ws] of currentRefs.entries()) {
        currentRefs.delete(slug);
        ws.close();
      }
    };
    // slugs array identity is stable in practice (derived from constant)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const markAllRead = useCallback(() => {
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
  }, []);

  const unread = alerts.filter((a) => !a.read).length;
  return { alerts, unread, markAllRead };
}

function cents(v: number): string {
  return `${Math.round(v * 100)}¢`;
}

export function NotificationBell({ slugs }: { slugs: string[] }) {
  const [open, setOpen] = useState(false);
  const { alerts, unread, markAllRead } = useGlobalPriceAlerts(slugs);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [open]);

  const handleToggle = () => {
    setOpen((v) => {
      if (!v) markAllRead();
      return !v;
    });
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={handleToggle}
        aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ""}`}
        className="relative grid h-10 w-10 place-items-center rounded-xl border border-border text-muted transition hover:border-border-light hover:text-text"
      >
        <BellIcon />
        {unread > 0 && (
          <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-0.5 font-mono text-[10px] font-black text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-50 w-80 rounded-xl border border-border bg-surface shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-muted">
              Price Alerts
            </span>
            {alerts.length > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-accent hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          <ul className="max-h-80 overflow-y-auto">
            {alerts.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-muted">
                No alerts yet
              </li>
            ) : (
              alerts.map((alert) => (
                <li
                  key={alert.id}
                  className={cn(
                    "border-b border-border/50 px-4 py-3 text-sm last:border-0",
                    !alert.read && "bg-accent/5",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-text">{alert.slug}</span>
                    <span className="font-mono text-xs text-muted">
                      {new Date(alert.ts * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-muted">
                    YES {cents(alert.yes)} · NO {cents(alert.no)}
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
