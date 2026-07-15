"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  subscribeNotificationsWS,
  type NotificationItem,
} from "@/lib/notifications-api";

function relativeTime(value: string | null): string {
  if (!value) return "";
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60_000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

function tokenSubject(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as { sub?: unknown };
    return typeof decoded.sub === "string" ? decoded.sub : null;
  } catch {
    return null;
  }
}

export function NotificationBell() {
  const { token, isReady } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!isReady || !token) {
      setItems([]);
      setUnreadCount(0);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchNotifications(token).then((page) => {
      if (cancelled) return;
      setItems(page.items);
      setUnreadCount(page.unread_count);
      setLoading(false);
    });
    const unsubscribe = subscribeNotificationsWS((incoming) => {
      if (cancelled) return;
      setItems((current) =>
        current.some((item) => item.id === incoming.id) ? current : [incoming, ...current].slice(0, 50),
      );
      setUnreadCount((count) => count + 1);
    }, tokenSubject(token));
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [isReady, token]);

  useEffect(() => {
    if (!open) return;
    function onOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [open]);

  async function handleRead(item: NotificationItem) {
    if (!token || !item.unread) return;
    setBusyId(item.id);
    const result = await markNotificationRead(token, item.id);
    setBusyId(null);
    if (!result) {
      setError("Could not mark that notification read. Try again.");
      return;
    }
    setItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, unread: false, read_at: result.read_at } : entry));
    setUnreadCount((count) => Math.max(0, count - 1));
  }

  async function handleMarkAllRead() {
    if (!token || unreadCount === 0) return;
    setBusyId("all");
    const result = await markAllNotificationsRead(token);
    setBusyId(null);
    if (!result) {
      setError("Could not mark notifications read. Try again.");
      return;
    }
    setItems((current) => current.map((item) => ({ ...item, unread: false, read_at: item.read_at ?? new Date().toISOString() })));
    setUnreadCount(0);
  }

  const label = !token ? "Log in to see notifications" : `Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`;

  return (
    <aside ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={label}
        className="relative grid h-10 w-10 place-items-center rounded-xl border border-border text-muted transition hover:border-border-light hover:text-text"
      >
        <BellIcon />
        {unreadCount > 0 ? (
          <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-0.5 font-mono text-[10px] font-black text-bg">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <section className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-xl border border-border bg-surface shadow-xl" aria-label="Notification center">
          <header className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-xs font-black uppercase tracking-wider text-text">Notifications</h2>
            {token && unreadCount > 0 ? (
              <button
                type="button"
                onClick={() => void handleMarkAllRead()}
                disabled={busyId === "all"}
                className="min-h-8 rounded-lg px-2 text-xs font-bold text-accent transition hover:bg-accent/10 disabled:opacity-50"
              >
                {busyId === "all" ? "Saving…" : "Mark all read"}
              </button>
            ) : null}
          </header>
          {error ? <p role="alert" className="border-b border-danger/30 bg-danger-dim px-4 py-2 text-xs text-danger">{error}</p> : null}
          {!token ? (
            <p className="px-4 py-6 text-center text-sm text-muted">
              <Link href="/auth/login" className="font-bold text-accent-bright hover:underline">Log in</Link> to see order and follow notifications.
            </p>
          ) : loading ? (
            <p className="px-4 py-6 text-center text-sm text-muted">Loading notifications…</p>
          ) : items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">You’re up to date. New paper-order activity will appear here.</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {items.map((item) => {
                const content = (
                  <>
                    <p className="flex items-start justify-between gap-3">
                      <span className="font-bold text-text">{item.title}</span>
                      <time className="shrink-0 font-mono text-[10px] text-muted-2" dateTime={item.created_at ?? undefined}>{relativeTime(item.created_at)}</time>
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted">{item.body}</p>
                  </>
                );
                return (
                  <li key={item.id} className={`border-b border-border/60 last:border-0 ${item.unread ? "bg-accent/5" : ""}`}>
                    {item.link?.startsWith("/") ? (
                      <Link href={item.link} onClick={() => void handleRead(item)} className="block px-4 py-3 transition hover:bg-surface-2">
                        {content}
                      </Link>
                    ) : (
                      <button type="button" onClick={() => void handleRead(item)} disabled={busyId === item.id} className="block w-full px-4 py-3 text-left transition hover:bg-surface-2 disabled:opacity-60">
                        {content}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      ) : null}
    </aside>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
