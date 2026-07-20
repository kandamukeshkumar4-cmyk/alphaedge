"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { VenueImage } from "@/components/VenueImage";
import type { SignalAlert, SignalAlertOutcome } from "@/hooks/useSignalAlerts";

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

const volumeFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function formatVolume(value: number): string {
  return `$${volumeFormatter.format(value)}`;
}

/** Payout multiple for a real stored price (1 / price). Omitted at 0 — never
 * divide by zero and show an invented number. */
function formatMultiplier(price: number): string | null {
  if (price <= 0) {
    return null;
  }
  return `${(1 / price).toFixed(2)}x`;
}

function formatPct(price: number): string {
  return `${Math.round(price * 100)}%`;
}

type AlertToastCardProps = {
  toast: SignalAlert;
  dismissing?: boolean;
};

function OutcomeAvatar({
  outcome,
  glyph,
}: {
  outcome: SignalAlertOutcome;
  glyph: string;
}) {
  return (
    <VenueImage
      src={outcome.imageUrl}
      alt=""
      className="h-6 w-6 shrink-0 rounded-full border border-border object-cover"
      fallback={
        <span
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-border bg-bg/60 text-[11px]"
          aria-hidden
        >
          {glyph}
        </span>
      }
    />
  );
}

function OutcomeRow({ outcome, glyph }: { outcome: SignalAlertOutcome; glyph: string }) {
  const isNo = outcome.name.trim().toLowerCase() === "no";
  // Branded accents only — Yes mint / No blue, never danger-red.
  const accent = isNo ? "border-secondary/70" : "border-primary/70";
  const pill = isNo ? "bg-secondary-dim text-secondary" : "bg-primary-dim text-primary";
  const multiplier = formatMultiplier(outcome.price);
  return (
    <div className="flex items-center gap-2">
      <OutcomeAvatar outcome={outcome} glyph={glyph} />
      <span className={cn("truncate border-b-2 pb-px text-[13px] font-semibold text-text", accent)}>
        {outcome.name}
      </span>
      {multiplier !== null ? (
        <span className="ml-auto font-mono text-xs tabular text-muted">{multiplier}</span>
      ) : (
        <span className="ml-auto" />
      )}
      <span
        className={cn(
          "shrink-0 rounded-full px-2 py-0.5 font-mono text-[11px] font-bold tabular",
          pill,
        )}
      >
        {formatPct(outcome.price)}
      </span>
    </div>
  );
}

/**
 * Loop V78 (N3) — Polymarket-style mobile alert card. Pure presentational
 * component (no effects/timers) so it renders synchronously and stays
 * unit-testable; AlertToast below owns the lifetime choreography.
 *
 * Layout mirrors the venue's mobile cards: category icon + tiny label, bold
 * two-line market question, up to two outcome rows (entity avatar + name with
 * accent underline + multiplier + % pill), muted volume/count footer. Every
 * number/image is real stored data — missing pieces are omitted or fall back
 * to the glyph token, never fabricated.
 */
export function AlertToastCard({ toast, dismissing = false }: AlertToastCardProps) {
  const style = signalStyle(toast.signalType);
  const tint = TINT[style.tint] ?? TINT.primary;
  const title = formatMarketTitle(toast.marketTitle);
  const glyph = toast.icon ?? style.glyph;
  const headerLabel = toast.categoryLabel ?? style.kicker;
  // Whole card is the View affordance: deep-link to the market when it is
  // mirrored locally (a stored market row enriched this alert), else /signals.
  const mirrored = toast.categoryLabel !== null;
  const href = mirrored ? `/markets/${toast.marketSlug}` : "/signals";
  const footerRight =
    toast.marketCount !== null && toast.marketCount > 1
      ? `${toast.marketCount} markets`
      : toast.traders !== null && toast.traders > 0
        ? `${volumeFormatter.format(toast.traders)} traders`
        : null;

  return (
    <Link
      href={href}
      aria-label={`View ${title}`}
      className={cn(
        "alert-toast-enter group pointer-events-auto relative block overflow-hidden rounded-2xl border bg-surface-2/95 backdrop-blur-sm",
        tint.ring,
        tint.glow,
        dismissing && "alert-toast-exit",
      )}
    >
      {/* Accent progress bar that drains over the toast lifetime */}
      <span
        className={cn("block h-0.5 w-full origin-left alert-toast-bar opacity-60", tint.dot)}
        aria-hidden
      />
      <div className="flex flex-col gap-2 p-3.5">
        {/* Header: category icon (real venue image or glyph) + tiny label +
            the signal kicker on the right. */}
        <div className="alert-toast-rise-1 flex items-center gap-2">
          <VenueImage
            src={toast.imageUrl}
            alt=""
            className="h-7 w-7 shrink-0 rounded-lg border border-border object-cover"
            fallback={
              <span
                className={cn(
                  "grid h-7 w-7 shrink-0 place-items-center rounded-lg border bg-bg/60 text-sm",
                  tint.ring,
                )}
                aria-hidden
              >
                {glyph}
              </span>
            }
          />
          <p className="truncate text-[10px] font-bold uppercase tracking-[0.1em] text-muted">
            {headerLabel}
          </p>
          <span
            className={cn(
              "ml-auto flex shrink-0 items-center gap-1 text-[10px] font-semibold",
              tint.text,
            )}
          >
            <span aria-hidden>{style.glyph}</span>
            {style.kicker}
          </span>
        </div>

        {/* Bold market question, clamped to two lines like the venue card. */}
        <p className="alert-toast-rise-2 line-clamp-2 text-[15px] font-bold leading-snug text-text">
          {title}
        </p>

        {/* Outcome rows — only when real stored prices exist. */}
        {toast.outcomes.length > 0 ? (
          <div className="alert-toast-rise-3 flex flex-col gap-1.5">
            {toast.outcomes.slice(0, 2).map((outcome) => (
              <OutcomeRow key={outcome.name} outcome={outcome} glyph={glyph} />
            ))}
          </div>
        ) : null}

        {/* Muted footer: real volume left, real market/trader count right. */}
        {toast.volume !== null || footerRight !== null ? (
          <div className="alert-toast-rise-4 flex items-center text-[10px] text-muted">
            {toast.volume !== null ? (
              <span className="font-mono tabular">{formatVolume(toast.volume)} vol</span>
            ) : null}
            <span className="ml-auto inline-flex items-center gap-1">
              {footerRight !== null ? <span className="font-mono tabular">{footerRight}</span> : null}
              <span
                className={cn("text-xs transition-transform group-hover:translate-x-0.5", tint.text)}
                aria-hidden
              >
                →
              </span>
            </span>
          </div>
        ) : null}
      </div>
    </Link>
  );
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
        <AlertToastCard key={toast.id} toast={toast} dismissing={toast.dismissing} />
      ))}
    </div>
  );
}
