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
    .replace(/-\d{2,3}-\d{2,3}$/, "") // trailing strike ranges like -140-159
    .split("-")
    .filter(Boolean);
  const text = words.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Per-signal-type identity: emoji glyph + short kicker + accent tint. Every
// signal is INFORMATIONAL (not an error), so tints are branded, never danger.
type SignalStyle = { glyph: string; kicker: string; tint: string };

function signalStyle(rawType: string): SignalStyle {
  const key = (rawType.split(":").pop() ?? rawType).toLowerCase();
  const map: Record<string, SignalStyle> = {
    price_jump: { glyph: "⚡", kicker: "Price jump", tint: "primary" },
    whale_delta: { glyph: "🐋", kicker: "Whale move", tint: "secondary" },
    news_arrival: { glyph: "📰", kicker: "Fresh news", tint: "secondary" },
    momentum: { glyph: "📈", kicker: "Momentum", tint: "primary" },
    expiry_fade: { glyph: "⏳", kicker: "Expiry fade", tint: "amber" },
    arb: { glyph: "🎯", kicker: "Arb edge", tint: "primary" },
    arbitrage: { glyph: "🎯", kicker: "Arb edge", tint: "primary" },
    alignment: { glyph: "🧭", kicker: "Alignment", tint: "secondary" },
    forecast: { glyph: "🔮", kicker: "Forecast", tint: "primary" },
  };
  return map[key] ?? { glyph: "📡", kicker: formatSignalType(rawType), tint: "primary" };
}

const TINT: Record<string, { ring: string; text: string; dot: string; glow: string }> = {
  primary: {
    ring: "border-primary/40",
    text: "text-primary",
    dot: "bg-primary",
    glow: "shadow-[0_0_24px_-6px_rgba(0,232,176,0.45)]",
  },
  secondary: {
    ring: "border-secondary/40",
    text: "text-secondary",
    dot: "bg-secondary",
    glow: "shadow-[0_0_24px_-6px_rgba(75,158,255,0.45)]",
  },
  amber: {
    ring: "border-amber-400/40",
    text: "text-amber-300",
    dot: "bg-amber-400",
    glow: "shadow-[0_0_24px_-6px_rgba(251,191,36,0.4)]",
  },
};

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
      {visible.map((toast) => {
        const style = signalStyle(toast.signalType);
        const tint = TINT[style.tint] ?? TINT.primary;
        return (
          <article
            key={toast.id}
            className={cn(
              "alert-toast-enter group pointer-events-auto overflow-hidden rounded-2xl border bg-surface-2/95 backdrop-blur-sm",
              tint.ring,
              tint.glow,
              toast.dismissing && "alert-toast-exit",
            )}
          >
            {/* Accent progress bar that drains over the toast lifetime */}
            <span
              className={cn("block h-0.5 w-full origin-left alert-toast-bar", tint.dot)}
              aria-hidden
            />
            <div className="flex items-center gap-3 p-3">
              {/* Signal glyph in a tinted, softly-pulsing token */}
              <div
                className={cn(
                  "relative grid h-10 w-10 shrink-0 place-items-center rounded-xl border bg-bg/40 text-lg",
                  tint.ring,
                )}
                aria-hidden
              >
                <span className={cn("absolute inset-0 rounded-xl alert-toast-pulse", tint.dot, "opacity-20")} />
                <span className="relative">{style.glyph}</span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className={cn("h-1.5 w-1.5 rounded-full alert-toast-pulse", tint.dot)} aria-hidden />
                  <p className={cn("text-[11px] font-bold uppercase tracking-[0.08em]", tint.text)}>
                    {style.kicker}
                  </p>
                  <span className="ml-auto rounded-full border border-border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted">
                    Signal
                  </span>
                </div>
                <p className="mt-0.5 truncate text-sm font-semibold text-text">
                  {formatMarketTitle(toast.marketTitle)}
                </p>
                {toast.confidencePct !== null ? (
                  <p className="mt-0.5 text-[11px] text-muted">
                    Confidence{" "}
                    <span className={cn("font-mono font-bold", tint.text)}>{toast.confidencePct}%</span>
                  </p>
                ) : null}
              </div>
              <Link
                href="/signals"
                className={cn(
                  "shrink-0 self-center rounded-lg border px-3 py-1.5 text-xs font-bold transition group-hover:brightness-110",
                  tint.ring,
                  tint.text,
                  "hover:bg-bg/40",
                )}
              >
                View →
              </Link>
            </div>
          </article>
        );
      })}
    </div>
  );
}
