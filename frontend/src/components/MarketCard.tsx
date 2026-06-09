import Link from "next/link";

import type { Market } from "@/lib/markets-api";
import { cn } from "@/lib/cn";
import { formatProbabilityAxis } from "@/lib/probability-format";

const PLATFORM_STYLES: Record<string, string> = {
  Polymarket: "border-[#5B4FE8]/35 bg-[#5B4FE8]/15 text-[#B4ABFF]",
  Kalshi: "border-primary/35 bg-primary/15 text-primary",
};

function platformBadgeClass(platform: string): string {
  return PLATFORM_STYLES[platform] ?? "border-border bg-surface-2 text-muted";
}

function statusLabel(status: string): "Open" | "Resolved" {
  return status === "resolved" ? "Resolved" : "Open";
}

export function MarketCard({ market }: { market: Market }) {
  const impliedPct =
    market.implied_yes != null ? Math.round(market.implied_yes * 100) : null;

  return (
    <Link
      href={`/markets/${market.slug}`}
      className="group flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-accent hover:bg-surface-2 hover:shadow-glow"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted">
            {market.category}
          </p>
          <h3 className="mt-1.5 line-clamp-2 text-base font-black leading-snug text-text">
            {market.title}
          </h3>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.06em]",
            platformBadgeClass(market.platform),
          )}
        >
          {market.platform}
        </span>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-xs font-semibold">
          <span className="text-muted">Implied YES</span>
          <span className="font-mono font-bold text-text tabular">
            {impliedPct != null ? formatProbabilityAxis(market.implied_yes!) : "—"}
          </span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary/80 to-primary transition-all"
            style={{ width: impliedPct != null ? `${impliedPct}%` : "0%" }}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.06em]",
            statusLabel(market.status) === "Open"
              ? "bg-accent/15 text-accent"
              : "bg-muted/15 text-muted",
          )}
        >
          {statusLabel(market.status)}
        </span>
        <span className="text-xs font-semibold text-muted transition group-hover:text-accent">
          View market →
        </span>
      </div>
    </Link>
  );
}

export function MarketCardSkeleton() {
  return (
    <div
      aria-hidden
      className="animate-pulse rounded-2xl border border-border bg-surface p-4 shadow-card"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <div className="h-3 w-16 rounded bg-surface-2" />
          <div className="h-5 w-4/5 rounded bg-surface-2" />
          <div className="h-5 w-3/5 rounded bg-surface-2" />
        </div>
        <div className="h-6 w-20 rounded-full bg-surface-2" />
      </div>
      <div className="mt-4 space-y-2">
        <div className="h-3 w-24 rounded bg-surface-2" />
        <div className="h-2 rounded-full bg-surface-2" />
      </div>
      <div className="mt-4 flex justify-between border-t border-border pt-3">
        <div className="h-6 w-14 rounded-full bg-surface-2" />
        <div className="h-4 w-24 rounded bg-surface-2" />
      </div>
    </div>
  );
}
