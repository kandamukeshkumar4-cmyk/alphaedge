"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { RollingPrice } from "@/components/RollingPrice";
import { useLivePrice } from "@/context/live-prices";
import { formatCompactUSD, type Market } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

export function PolymarketMarketCard({ market }: { market: Market }) {
  const yes = market.outcomes[0];
  const no = market.outcomes[1];
  const live = useLivePrice(market.slug, yes?.price ?? 0);
  const yesPrice = live.price > 0 || live.connected ? live.price : (yes?.price ?? 0);
  const noPrice = no ? (live.price > 0 || live.connected ? 1 - live.price : no.price) : 1 - yesPrice;
  const showYes = yesPrice > 0 || live.connected;

  return (
    <Link
      href={marketHref(market.slug)}
      className="group flex flex-col overflow-hidden rounded-2xl border border-[#5B4FE8]/25 bg-[#12131a] transition hover:border-[#5B4FE8]/55 hover:shadow-[0_0_24px_rgba(91,79,232,0.12)]"
    >
      <div className="flex gap-3 p-4">
        <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-surface-2">
          {market.imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={market.imageUrl}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : (
            <span className="flex h-full w-full items-center justify-center text-2xl">
              {market.icon || "📊"}
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-[#5B4FE8]/15 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider text-[#B4ABFF]">
              Polymarket
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">
              {market.category}
            </span>
          </div>
          <h3 className="mt-1.5 line-clamp-2 text-[15px] font-bold leading-snug text-text group-hover:text-[#B4ABFF]">
            {market.title}
          </h3>
        </div>
      </div>

      <div className="mt-auto grid grid-cols-2 gap-2 px-4 pb-4">
        <span className="flex flex-col items-center rounded-xl border border-emerald-500/35 bg-emerald-500/10 px-3 py-2.5 text-center transition group-hover:border-emerald-500/55">
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400/90">
            Yes
          </span>
          <RollingPrice
            value={showYes ? yesPrice : null}
            flash={live.flash}
            className="mt-0.5 text-lg text-emerald-300"
          />
        </span>
        <span className="flex flex-col items-center rounded-xl border border-red-500/35 bg-red-500/10 px-3 py-2.5 text-center transition group-hover:border-red-500/55">
          <span className="text-[10px] font-bold uppercase tracking-wider text-red-400/90">
            No
          </span>
          <RollingPrice
            value={showYes ? noPrice : null}
            className="mt-0.5 text-lg text-red-300"
          />
        </span>
      </div>

      <div className="flex items-center justify-between border-t border-[#5B4FE8]/15 bg-[#0e0f16] px-4 py-2.5 text-[11px] font-mono text-muted">
        <span>{formatCompactUSD(market.volume)} vol</span>
        <span className={cn(market.status === "resolved" && "text-muted-2")}>
          {market.status === "resolved" ? "Resolved" : "Open"}
        </span>
      </div>
    </Link>
  );
}

export function PolymarketCardSkeleton() {
  return (
    <div className="animate-pulse overflow-hidden rounded-2xl border border-[#5B4FE8]/20 bg-[#12131a]">
      <div className="flex gap-3 p-4">
        <div className="h-14 w-14 rounded-xl bg-surface-2" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-20 rounded bg-surface-2" />
          <div className="h-4 w-full rounded bg-surface-2" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 px-4 pb-4">
        <div className="h-16 rounded-xl bg-surface-2" />
        <div className="h-16 rounded-xl bg-surface-2" />
      </div>
    </div>
  );
}
