import Link from "next/link";

import type { Market } from "@/lib/markets-api";
import { cn } from "@/lib/cn";

/*
 * QuestFlow-anatomy market card for the live catalog (markets-api shape):
 * icon tile + title, platform/status meta row, an outcome row with the YES
 * price in teal cents and tinted Yes/No buttons, then the outlined
 * "AI Analyze" action. Paper-trading only.
 */

const CATEGORY_ICON: Record<string, string> = {
  NBA: "🏀",
  "FIFA WC2026": "⚽",
  Elections: "🗳️",
  Crypto: "₿",
  Culture: "🎬",
  Economics: "📊",
};

function centsLabel(probability: number | null): string {
  if (probability == null) return "—";
  return `${Math.round(probability * 100)}¢`;
}

export function MarketCard({ market }: { market: Market }) {
  const resolved = market.status === "resolved" || market.resolution_outcome != null;
  const winner = market.resolution_outcome?.toUpperCase();
  const yes = market.implied_yes;

  return (
    <div
      className={cn(
        "flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:border-border-light",
        resolved && "opacity-75",
      )}
    >
      <div className="flex items-start gap-4">
        <span className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-surface-3 text-2xl">
          {CATEGORY_ICON[market.category] ?? "📈"}
        </span>
        <div className="min-w-0 flex-1">
          <Link href={`/markets/${market.slug}`} className="block">
            <h3 className="line-clamp-2 text-lg font-bold leading-snug text-text hover:text-primary">
              {market.title}
            </h3>
          </Link>
          <div className="mt-2 flex items-center justify-between text-sm text-muted">
            <span>{market.platform}</span>
            <span>
              {resolved ? (
                <span className="font-semibold text-danger">
                  Resolved{winner === "YES" || winner === "NO" ? ` · ${winner}` : ""}
                </span>
              ) : (
                "Open"
              )}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2.5">
        <span className="min-w-0 flex-1 truncate text-base font-medium text-text">Yes</span>
        <span className="shrink-0 text-base font-bold tabular-nums text-primary">
          {centsLabel(yes)}
        </span>
        <Link
          href={`/markets/${market.slug}?side=yes`}
          className="grid h-10 w-[72px] shrink-0 place-items-center rounded-xl bg-primary-dim text-sm font-semibold text-primary transition hover:bg-primary hover:text-bg"
        >
          Yes
        </Link>
        <Link
          href={`/markets/${market.slug}?side=no`}
          className="grid h-10 w-[72px] shrink-0 place-items-center rounded-xl bg-danger-dim text-sm font-semibold text-danger transition hover:bg-danger hover:text-white"
        >
          No
        </Link>
      </div>

      <Link
        href={`/markets/${market.slug}#ai`}
        className="mt-4 flex h-12 items-center justify-center gap-2 rounded-xl border border-primary/45 text-base font-medium text-primary transition hover:bg-primary-dim"
      >
        <SparkIcon />
        AI Analyze
      </Link>
    </div>
  );
}

export function MarketCardSkeleton() {
  return (
    <div
      aria-hidden
      className="animate-pulse rounded-2xl border border-border bg-surface p-4 shadow-card"
    >
      <div className="flex items-start gap-4">
        <div className="h-14 w-14 rounded-xl bg-surface-2" />
        <div className="flex-1 space-y-2">
          <div className="h-5 w-4/5 rounded bg-surface-2" />
          <div className="h-4 w-3/5 rounded bg-surface-2" />
        </div>
      </div>
      <div className="mt-4 h-10 rounded-xl bg-surface-2" />
      <div className="mt-3 h-12 rounded-xl bg-surface-2" />
    </div>
  );
}

function SparkIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" strokeLinejoin="round" />
      <path d="M19 3l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z" strokeLinejoin="round" />
    </svg>
  );
}
