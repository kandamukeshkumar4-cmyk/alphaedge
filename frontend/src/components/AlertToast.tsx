"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import type { SignalAlert } from "@/hooks/useSignalAlerts";

const TOAST_LIFETIME_MS = 5_000;

type VisibleToast = SignalAlert & { dismissing: boolean };

function formatSignalType(value: string): string {
  return value
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

type AlertToastProps = {
  alerts: SignalAlert[];
};

export function AlertToast({ alerts }: AlertToastProps) {
  const shownIdsRef = useRef<Set<string>>(new Set());
  const timersRef = useRef<Map<string, number>>(new Map());
  const [visible, setVisible] = useState<VisibleToast[]>([]);

  useEffect(() => {
    const fresh = alerts.filter((alert) => !shownIdsRef.current.has(alert.id));
    if (fresh.length === 0) {
      return;
    }

    fresh.forEach((alert) => {
      shownIdsRef.current.add(alert.id);
      const fadeTimer = window.setTimeout(() => {
        setVisible((prev) =>
          prev.map((item) => (item.id === alert.id ? { ...item, dismissing: true } : item)),
        );
      }, TOAST_LIFETIME_MS - 400);

      const removeTimer = window.setTimeout(() => {
        setVisible((prev) => prev.filter((item) => item.id !== alert.id));
        timersRef.current.delete(alert.id);
      }, TOAST_LIFETIME_MS);

      timersRef.current.set(alert.id, fadeTimer);
      timersRef.current.set(`${alert.id}:remove`, removeTimer);
    });

    setVisible((prev) => [...prev, ...fresh.map((alert) => ({ ...alert, dismissing: false }))]);
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
            "alert-toast-enter pointer-events-auto rounded-xl border border-danger/35 bg-surface-2 p-3 shadow-lift",
            toast.dismissing && "alert-toast-exit",
          )}
        >
          <div className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-danger" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold uppercase tracking-[0.06em] text-danger">
                New {formatSignalType(toast.signalType)} signal
              </p>
              <p className="mt-0.5 truncate text-sm font-semibold text-text">{toast.marketTitle}</p>
              <p className="mt-0.5 text-xs text-muted">
                Confidence{" "}
                <span className="font-mono font-bold text-text">
                  {toast.confidencePct === null ? "—" : `${toast.confidencePct}%`}
                </span>
              </p>
            </div>
          </div>
          <div className="mt-3 flex justify-end">
            <Link
              href="/signals"
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-bold text-white transition hover:brightness-110"
            >
              View
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
