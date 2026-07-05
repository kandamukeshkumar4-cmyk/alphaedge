"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { RollingPrice } from "@/components/RollingPrice";
import { useLivePrice } from "@/context/live-prices";
import { isKalshiMatchCard } from "@/lib/hero-market";
import { resolveOutcomeSlug } from "@/lib/live-price";
import { formatCompactUSD, type Market, type MarketOutcome } from "@/lib/mock-data";
import { flagForTeam } from "@/lib/team-flags";
import { cn } from "@/lib/cn";

function platformLabel(source: string | undefined): string {
  const key = (source ?? "").toLowerCase();
  if (key === "kalshi") return "Kalshi";
  if (key === "polymarket") return "Polymarket";
  if (key === "seed") return "Paper";
  return "Live";
}

function OutcomeChip({
  outcome,
  market,
  highlight,
}: {
  outcome: MarketOutcome;
  market: Market;
  highlight: boolean;
}) {
  const slug = resolveOutcomeSlug(outcome.id, market.slug);
  const live = useLivePrice(slug, outcome.price);
  const price = live.price > 0 || live.connected ? live.price : outcome.price;
  const showPrice = price > 0 || live.connected;
  const isYes = outcome.id === "yes" || outcome.label.toUpperCase() === "YES";
  const isNo = outcome.id === "no" || outcome.label.toUpperCase() === "NO";
  const isTie = /tie|draw/i.test(outcome.label);

  return (
    <span
      className={cn(
        "inline-flex min-w-[76px] flex-col items-center rounded-md border px-3 py-2 text-center transition",
        isYes && "border-[#05b169]/50 bg-[#05b169]/10",
        isNo && "border-red-500/40 bg-red-500/10",
        !isYes && !isNo && highlight && !isTie && "border-[#05b169]/40 bg-[#05b169]/5",
        !isYes && !isNo && !highlight && "border-white/15 bg-white/5",
        isTie && "border-white/15 bg-white/5",
      )}
    >
      <span className="text-[10px] font-bold uppercase tracking-wide text-white/50">
        {isYes || isNo ? outcome.label : (
          <span className="flex items-center gap-0.5">
            {flagForTeam(outcome.label)}
            <span className="max-w-[56px] truncate">{outcome.label}</span>
          </span>
        )}
      </span>
      <RollingPrice
        value={showPrice ? price : null}
        flash={live.flash}
        cents
        className={cn(
          "mt-0.5 font-mono text-sm font-bold tabular",
          isYes && "text-[#05b169]",
          isNo && "text-red-400",
          !isYes && !isNo && "text-white",
        )}
      />
    </span>
  );
}

export function KalshiDiscoveryRow({ market }: { market: Market }) {
  const isMatch = isKalshiMatchCard(market);
  const outcomes = market.outcomes.slice(0, isMatch ? 4 : 2);
  const favorite = outcomes.reduce(
    (best, o) => (o.price > best.price ? o : best),
    outcomes[0] ?? { price: 0, id: "", label: "", emoji: "", prevPrice: 0, tone: "muted" as const },
  );

  return (
    <Link
      href={marketHref(market.slug)}
      className="group flex flex-col gap-3 border-b border-white/8 px-3 py-4 transition hover:bg-white/[0.03] sm:flex-row sm:items-center sm:gap-6"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-white/40">
          <span>{market.category}</span>
          <span>·</span>
          <span>{platformLabel(market.source)}</span>
        </div>
        <h3 className="mt-1 line-clamp-2 text-[15px] font-semibold leading-snug text-white group-hover:text-[#05b169]">
          {market.title}
        </h3>
        <p className="mt-1 font-mono text-xs tabular text-white/40">
          {formatCompactUSD(market.volume)} vol
        </p>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
        {outcomes.map((outcome) => (
          <OutcomeChip
            key={outcome.id}
            outcome={outcome}
            market={market}
            highlight={outcome.id === favorite.id}
          />
        ))}
      </div>
    </Link>
  );
}

export function KalshiDiscoverySkeleton() {
  return (
    <div className="animate-pulse border-b border-white/8 px-3 py-4">
      <div className="flex gap-4">
        <div className="flex-1 space-y-2">
          <div className="h-3 w-24 rounded bg-white/10" />
          <div className="h-5 w-4/5 max-w-md rounded bg-white/10" />
        </div>
        <div className="flex gap-2">
          <div className="h-14 w-[76px] rounded-md bg-white/10" />
          <div className="h-14 w-[76px] rounded-md bg-white/10" />
        </div>
      </div>
    </div>
  );
}
