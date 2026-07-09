"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLivePrice } from "@/context/live-prices";
import { useLiveSparkline } from "@/hooks/useLiveSparkline";
import { Sparkline } from "@/components/Sparkline";
import { cn } from "@/lib/cn";
import { formatCompactUSD, type Market } from "@/lib/mock-data";
import { marketHref } from "@/lib/market-href";
import { useAtlasPanel } from "@/context/atlas-panel";

// Questflow-style grid card: name, live price, 24h change, volume, sparkline,
// then Long / Short / AI Analyze action row.
export function QuestMarketCard({ market }: { market: Market }) {
  const router = useRouter();
  const { openPanel } = useAtlasPanel();
  const fallback = market.outcomes[0]?.price ?? 0.5;
  const live = useLivePrice(market.slug, fallback);
  const spark = useLiveSparkline(market.slug, fallback, market.source);
  const up = spark.data.length > 1 ? spark.up : live.deltaPts >= 0;
  const pricePct = Math.round(live.price * 100);

  return (
    <div
      className={cn(
        "group flex flex-col rounded-[10px] border border-border bg-surface p-3 transition hover:border-border-light hover:shadow-card",
        live.flash === "up" && "animate-flash-green",
        live.flash === "down" && "animate-flash-red",
      )}
    >
      <Link href={marketHref(market.slug)} className="flex items-start gap-2">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface-3 text-sm">
          {market.icon || "◆"}
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-text group-hover:text-accent-bright">
            {market.title}
          </p>
          <p className="text-[10px] uppercase tracking-wide text-muted-2">
            {market.source === "kalshi" || market.source === "polymarket"
              ? `${market.source} · live`
              : market.category}
          </p>
        </div>
      </Link>

      <div className="mt-2 flex items-end justify-between">
        <p className="font-mono text-xl font-semibold tabular-nums text-text">
          {pricePct}
          <span className="text-xs text-muted-2">¢</span>
        </p>
        <div className="text-right">
          <p className={cn("font-mono text-[11px] font-semibold", up ? "text-primary" : "text-danger")}>
            {live.deltaPts >= 0 ? "+" : ""}
            {live.deltaPts} pts
          </p>
          <p className="text-[10px] text-muted-2">{formatCompactUSD(market.volume)} Vol.</p>
        </div>
      </div>

      <div className="mt-1.5 h-9">
        {spark.data.length > 1 ? (
          <Sparkline data={spark.data} up={up} width={260} height={36} className="h-full w-full" />
        ) : (
          <div className="skeleton h-full w-full rounded" />
        )}
      </div>

      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <button
          type="button"
          onClick={() => router.push(`/trade?slug=${encodeURIComponent(market.slug)}`)}
          className="rounded-md border border-primary/25 bg-primary-dim px-1.5 py-1 text-[11px] font-semibold text-primary transition hover:bg-primary hover:text-bg"
        >
          Analyze
        </button>
        <button
          type="button"
          onClick={() =>
            openPanel({
              mode: "analyze",
              marketSlug: market.slug,
              marketTitle: market.title,
              seedPrompt: `Analyze ${market.title}. Current YES ~${pricePct}¢.`,
            })
          }
          className="whitespace-nowrap rounded-md border border-primary/35 bg-primary-dim/50 px-1 py-1 text-[10px] font-semibold text-primary transition hover:bg-primary hover:text-bg"
        >
          ✦ AI Analyze
        </button>
      </div>
    </div>
  );
}

export function QuestMarketCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="skeleton h-9 w-9 rounded-full" />
      <div className="skeleton mt-3 h-4 w-3/4 rounded" />
      <div className="skeleton mt-2 h-7 w-1/3 rounded" />
      <div className="skeleton mt-3 h-10 w-full rounded" />
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="skeleton h-7 rounded-lg" />
        <div className="skeleton h-7 rounded-lg" />
        <div className="skeleton h-7 rounded-lg" />
      </div>
    </div>
  );
}
