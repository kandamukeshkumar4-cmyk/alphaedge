"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { LivePriceChip } from "@/components/notifications/LivePriceChip";
import { NotificationPrefsToggles } from "@/components/notifications/NotificationPrefsToggles";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  list,
  markAll,
  markRead,
  type NotificationV90,
} from "@/lib/notifications-api";

/*
 * Loop V90 (C2) — notification center: bell (mint unread badge, never
 * danger-red) + dropdown panel fed by the frozen loop90 contract client
 * (live-first, mandatory PAPER mock fallback — verifiable with no backend).
 * Skeletons reserve row height (no layout jump), empty state for a quiet
 * inbox, all motion rides the globals.css reduced-motion kill-switch.
 */

/** Pure: ISO timestamp → compact relative label ("now", "12m", "3h", "2d"). */
export function relativeTime(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60_000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

const TYPE_ICONS: Record<string, string> = {
  whale: "🐋",
  news: "📰",
  model: "🧠",
  price: "📈",
  resolution: "🏁",
  info: "💡",
};

function typeIcon(type: string): string {
  return TYPE_ICONS[type] ?? TYPE_ICONS.info;
}

export function NotificationCenter() {
  const { token, isReady } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationV90[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<"live" | "mock">("mock");
  const [busy, setBusy] = useState<string | null>(null);
  const rootRef = useRef<HTMLElement>(null);

  const load = useCallback(async () => {
    if (!isReady) return;
    setLoading(true);
    const result = await list(token ?? null, { limit: 30 });
    setItems(result.items);
    setUnread(result.unread);
    setSource(result.source);
    setLoading(false);
  }, [isReady, token]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function handleMarkOne(item: NotificationV90) {
    if (item.read) return;
    // Optimistic — the client never rejects; revert only on an explicit !ok.
    setItems((current) => current.map((entry) => (entry.id === item.id ? { ...entry, read: true } : entry)));
    setUnread((count) => Math.max(0, count - 1));
    const result = await markRead(item.id, token ?? null);
    if (!result.ok) {
      setItems((current) => current.map((entry) => (entry.id === item.id ? { ...entry, read: false } : entry)));
      setUnread((count) => count + 1);
    }
  }

  async function handleMarkAll() {
    if (unread === 0 || busy === "all") return;
    setBusy("all");
    setItems((current) => current.map((item) => ({ ...item, read: true })));
    setUnread(0);
    const result = await markAll(token ?? null);
    setBusy(null);
    if (!result.ok) {
      void load();
    }
  }

  const badgeCount = unread > 9 ? "9+" : String(unread);
  const label = unread > 0 ? `Notifications, ${badgeCount} unread` : "Notifications";

  return (
    <aside ref={rootRef} className="relative">
      <button
        type="button"
        data-testid="v90-notification-bell"
        onClick={() => setOpen((value) => !value)}
        aria-label={label}
        aria-expanded={open}
        title={label}
        className="relative grid h-10 w-10 place-items-center rounded-xl border border-border text-muted transition hover:border-border-light hover:text-text"
      >
        <BellGlyph />
        {unread > 0 ? (
          <span
            data-testid="notification-badge"
            className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-primary px-0.5 font-mono text-[10px] font-black text-bg"
          >
            {badgeCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <section
          role="region"
          aria-label="Notification center"
          className="absolute right-0 top-12 z-50 flex w-[min(24rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-lift motion-reduce:animate-none"
        >
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h2 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-text">
              Notifications
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em]",
                  source === "live"
                    ? "border-primary/40 bg-primary-dim/60 text-primary"
                    : "border-border-light bg-surface-2 text-muted-2",
                )}
                title={source === "live" ? "Live API" : "Paper mock — API offline"}
              >
                {source === "live" ? "live" : "paper mock"}
              </span>
            </h2>
            {unread > 0 ? (
              <button
                type="button"
                onClick={() => void handleMarkAll()}
                disabled={busy === "all"}
                className="min-h-8 rounded-lg px-2 text-xs font-bold text-primary transition hover:bg-primary/10 disabled:opacity-50"
              >
                {busy === "all" ? "Saving…" : "Mark all read"}
              </button>
            ) : null}
          </header>
          {source === "mock" ? (
            <p className="border-b border-border px-4 py-2 text-center text-xs text-muted-2">
              Showing demo notifications. These alerts are simulated, not live account events.
            </p>
          ) : null}

          {/* Reserved height: skeletons/empty states hold the panel steady. */}
          <div className="min-h-[196px]">
            {loading ? (
              <ul aria-hidden="true" className="divide-y divide-border/60">
                {[0, 1, 2].map((row) => (
                  <li key={row} className="flex items-start gap-3 px-4 py-3">
                    <span className="h-8 w-8 shrink-0 animate-pulse rounded-lg bg-surface-3 motion-reduce:animate-none" />
                    <span className="flex-1 space-y-2 pt-0.5">
                      <span className="block h-3 w-2/3 animate-pulse rounded bg-surface-3 motion-reduce:animate-none" />
                      <span className="block h-3 w-full animate-pulse rounded bg-surface-2 motion-reduce:animate-none" />
                    </span>
                  </li>
                ))}
              </ul>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center gap-1 px-4 py-10 text-center">
                <span aria-hidden="true" className="text-xl">🔔</span>
                <p className="text-sm font-semibold text-text">You&apos;re all caught up</p>
                <p className="text-xs text-muted">
                  New paper-trade activity and alerts will appear here.
                </p>
              </div>
            ) : (
              <ul className="max-h-96 overflow-y-auto">
                {items.map((item) => {
                  const inner = (
                    <>
                      <span
                        aria-hidden="true"
                        className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-border bg-primary-dim/40 text-sm"
                      >
                        {typeIcon(item.type)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-baseline justify-between gap-3">
                          <span className={cn("truncate text-[13px]", item.read ? "font-semibold text-muted" : "font-bold text-text")}>
                            {item.title}
                          </span>
                          <time
                            className="shrink-0 font-mono text-[10px] text-muted-2"
                            dateTime={item.created_at}
                          >
                            {relativeTime(item.created_at)}
                          </time>
                        </span>
                        <span className="mt-0.5 block text-xs leading-5 text-muted">{item.body}</span>
                      </span>
                      <span
                        aria-label={item.read ? undefined : "unread"}
                        className={cn(
                          "mt-1 h-2 w-2 shrink-0 rounded-full",
                          item.read ? "bg-transparent" : "bg-primary shadow-[0_0_8px_rgba(0,232,176,0.7)]",
                        )}
                      />
                    </>
                  );
                  const itemClass = cn(
                    "flex w-full items-start gap-3 border-b border-border/60 px-4 py-3 text-left transition last:border-0 hover:bg-surface-2",
                    !item.read && "bg-primary/[0.04]",
                  );
                  return (
                    <li key={item.id}>
                      {item.link && item.link.startsWith("/") ? (
                        <Link
                          href={item.link}
                          onClick={() => {
                            void handleMarkOne(item);
                            setOpen(false);
                          }}
                          className={itemClass}
                        >
                          {inner}
                        </Link>
                      ) : item.link ? (
                        <a
                          href={item.link}
                          onClick={() => void handleMarkOne(item)}
                          className={itemClass}
                        >
                          {inner}
                        </a>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleMarkOne(item)}
                          disabled={busy === item.id}
                          className={cn(itemClass, "disabled:opacity-60")}
                        >
                          {inner}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="border-t border-border bg-surface-2/30 px-4 py-2">
            <LivePriceChip />
          </div>

          <footer className="border-t border-border bg-surface-2/40 px-4 py-3">
            <NotificationPrefsToggles token={token ?? null} disabled={!isReady} />
          </footer>
        </section>
      ) : null}
    </aside>
  );
}

function BellGlyph() {
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
      aria-hidden="true"
    >
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
