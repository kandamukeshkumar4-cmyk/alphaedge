import Link from "next/link";

import type { Market } from "@/lib/markets-api";
import { cn } from "@/lib/cn";
import { formatProbabilityAxis } from "@/lib/probability-format";
import { AiEdge } from "@/components/ui/kit";

const PLATFORM_STYLES: Record<string, string> = {
  Polymarket: "border-accent/35 bg-accent/12 text-accent",
  Kalshi: "border-primary/35 bg-primary/15 text-primary",
};

// Deterministic per-market AI edge (demo signal) so cards feel QuestFlow-like
// without needing a live model call in the grid. Range roughly ±9 points.
function aiEdge(market: Market): number {
  let hash = 0;
  for (const ch of market.slug) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return ((Math.abs(hash) % 18) - 9);
}

const CATEGORY_BADGE_STYLES: Record<string, string> = {
  NBA: "border-accent/35 bg-accent/15 text-accent",
  "FIFA WC2026": "border-emerald-500/35 bg-emerald-500/15 text-emerald-400",
  Elections: "border-[#5B4FE8]/35 bg-[#5B4FE8]/15 text-[#B4ABFF]",
};

type CatalogCategory = keyof typeof CATEGORY_BADGE_STYLES;

function platformBadgeClass(platform: string): string {
  return PLATFORM_STYLES[platform] ?? "border-border bg-surface-2 text-muted";
}

function catalogCategory(market: Market): CatalogCategory | null {
  if (market.slug.startsWith("nba-") || market.category === "NBA") {
    return "NBA";
  }
  if (market.slug.startsWith("wc2026-") || market.category === "FIFA WC2026") {
    return "FIFA WC2026";
  }
  if (
    market.slug.startsWith("elect-") ||
    market.category === "Elections" ||
    market.category === "Politics"
  ) {
    return "Elections";
  }
  return null;
}

function statusLabel(status: string): "Open" | "Resolved" {
  return status === "resolved" ? "Resolved" : "Open";
}

function isResolvedMarket(market: Market): boolean {
  return market.status === "resolved" || market.resolution_outcome != null;
}

function winningOutcomeLabel(outcome: string | null): string | null {
  if (!outcome) {
    return null;
  }
  const normalized = outcome.toUpperCase();
  if (normalized === "YES" || normalized === "NO") {
    return normalized;
  }
  return null;
}

export function MarketCard({ market }: { market: Market }) {
  const impliedPct =
    market.implied_yes != null ? Math.round(market.implied_yes * 100) : null;
  const category = catalogCategory(market);
  const resolved = isResolvedMarket(market);
  const winner = winningOutcomeLabel(market.resolution_outcome);
  const edge = aiEdge(market);

  return (
    <Link
      href={`/markets/${market.slug}`}
      className={cn(
        "group flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-primary/45 hover:bg-surface-2 hover:shadow-glow",
        resolved && "opacity-75",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {category ? (
            <span
              className={cn(
                "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.08em]",
                CATEGORY_BADGE_STYLES[category],
              )}
            >
              {category}
            </span>
          ) : (
            <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted">
              {market.category}
            </p>
          )}
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

      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted-2">
            Implied YES
          </div>
          <div className="mt-0.5 font-mono text-3xl font-black leading-none tabular-nums text-text">
            {impliedPct != null ? formatProbabilityAxis(market.implied_yes!) : "—"}
          </div>
        </div>
        {!resolved ? <AiEdge value={`${edge >= 0 ? "+" : ""}${edge}%`} /> : null}
      </div>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary/70 to-primary transition-all"
          style={{ width: impliedPct != null ? `${impliedPct}%` : "0%" }}
        />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <div className="flex flex-wrap items-center gap-2">
          {resolved ? (
            <>
              <span className="rounded-full border border-red-500/35 bg-red-500/15 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.06em] text-red-300">
                RESOLVED
              </span>
              {winner === "YES" ? (
                <span className="rounded-full border border-emerald-500/35 bg-emerald-500/15 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.06em] text-emerald-300">
                  YES ✓
                </span>
              ) : null}
              {winner === "NO" ? (
                <span className="rounded-full border border-red-500/35 bg-red-500/15 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.06em] text-red-300">
                  NO ✓
                </span>
              ) : null}
            </>
          ) : (
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
          )}
        </div>
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
