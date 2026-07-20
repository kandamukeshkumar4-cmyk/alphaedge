"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import type { SignalAlert } from "@/hooks/useSignalAlerts";

const TOAST_LIFETIME_MS = 5_000;
const MAX_VISIBLE_TOASTS = 2;

// Module-level so SiteHeader / ATLAS remounts do not re-fire the same alerts
// (shownIds on a remounted component would otherwise be empty again).
const shownToastIds = new Set<string>();

type VisibleToast = SignalAlert & { dismissing: boolean };

function formatSignalType(value: string): string {
  // Raw enums arrive like "delta:price_jump" — keep only the meaningful tail
  // and humanize it ("Price jump"), never leak the namespace prefix.
  const tail = value.split(":").pop() ?? value;
  const words = tail.split(/[-_]/).filter(Boolean);
  const label = words.join(" ").toLowerCase();
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatMarketTitle(value: string): string {
  // Backend may send a raw slug (pm-foo-bar-2027 / ks-foo-30). Detect and
  // humanize it; leave real titles untouched.
  if (!/^(pm|ks)-/.test(value) && value.includes(" ")) return value;
  const words = value
    .replace(/^(pm|ks)-/, "")
    .replace(/-\d{6,}$/, "") // trailing numeric ids
    .split("-")
    .filter(Boolean);
  const text = words.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

type AlertToastProps = {
  alerts: SignalAlert[];
};

export function AlertToast({ alerts }: AlertToastProps) {
  const timersRef = useRef<Map<string, number>>(new Map());
  const [visible, setVisible] = useState<VisibleToast[]>([]);

  useEffect(() => {
    const fresh = alerts
      .filter((alert) => !shownToastIds.has(alert.id))
      .slice(0, MAX_VISIBLE_TOASTS);
    if (fresh.length === 0) {
      return;
    }

    fresh.forEach((alert) => {
      shownToastIds.add(alert.id);
      const fadeTimer = window.setTimeout(() => {
        setVisible((prev) =>
          prev.map((item) => (item.id === alert.id ? { ...item, dismissing: true } : item)),
        );
      }, TOAST_LIFETIME_MS - 400);

      const removeTimer = window.setTimeout(() => {
        setVisible((prev) => prev.filter((item) => item.id !== alert.id));
        timersRef.current.delete(alert.id);
        timersRef.current.delete(`${alert.id}:remove`);
      }, TOAST_LIFETIME_MS);

      timersRef.current.set(alert.id, fadeTimer);
      timersRef.current.set(`${alert.id}:remove`, removeTimer);
    });

    setVisible((prev) => {
      const next = [...prev, ...fresh.map((alert) => ({ ...alert, dismissing: false }))];
      return next.slice(-MAX_VISIBLE_TOASTS);
    });
  }, [alerts]);

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((timerId) => window.clearTimeout(timerId));
      timers.clear();
    };
  }, []);

  if (visible.length === 0) {
    return null;
  }

  return (
    <div
      className="pointer-events-none fixed right-4 top-[4.75rem] z-50 flex w-[min(92vw,360px)] flex-col gap-2"
      aria-live="polite"
    >
      {visible.map((toast) => (
        <article
          key={toast.id}
          className={cn(
            "alert-toast-enter pointer-events-auto rounded-xl border border-primary/30 bg-surface-2 p-3 shadow-lift",
            toast.dismissing && "alert-toast-exit",
          )}
        >
          <div className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold uppercase tracking-[0.06em] text-primary">
                {formatSignalType(toast.signalType)} signal
              </p>
              <p className="mt-0.5 truncate text-sm font-semibold text-text">
                {formatMarketTitle(toast.marketTitle)}
              </p>
              {toast.confidencePct !== null ? (
                <p className="mt-0.5 text-xs text-muted">
                  Confidence{" "}
                  <span className="font-mono font-bold text-text">{toast.confidencePct}%</span>
                </p>
              ) : null}
            </div>
          </div>
          <div className="mt-3 flex justify-end">
            <Link
              href="/signals"
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-bold text-bg transition hover:brightness-110"
            >
              View
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
