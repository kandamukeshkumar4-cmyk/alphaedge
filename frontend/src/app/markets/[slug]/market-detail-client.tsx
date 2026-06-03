"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getMarket,
  type Market,
  pct,
  multiplier,
  formatCompactUSD,
  timeUntil,
  toneClass,
} from "@/lib/mock-data";
import { PriceChart } from "@/components/PriceChart";
import { TradePanel } from "@/components/TradePanel";
import { OrderBook } from "@/components/OrderBook";
import { AIForecastPanel } from "@/components/AIForecastPanel";
import { MarketTabs } from "@/components/MarketTabs";
import { DecisionSignalPanel } from "@/components/DecisionSignalPanel";
import { cn } from "@/lib/cn";
import { fetchMarketDetail } from "@/lib/alphaedge-api";

export default function MarketDetailClient({ slug }: { slug: string }) {
  const [apiMarket, setApiMarket] = useState<Market | null>(null);
  const [loadedApi, setLoadedApi] = useState(false);
  const localMarket = getMarket(slug);
  const market = apiMarket ?? localMarket;

  useEffect(() => {
    let cancelled = false;
    fetchMarketDetail(slug).then((nextMarket) => {
      if (!cancelled) {
        setApiMarket(nextMarket);
        setLoadedApi(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (!market && loadedApi) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-20 text-center">
        <h1 className="text-2xl font-black">Market not found</h1>
        <Link href="/" className="mt-4 inline-block text-accent hover:underline">
          ← Back to markets
        </Link>
      </main>
    );
  }

  if (!market) {
    return (
      <main className="mx-auto max-w-[1400px] px-4 py-6">
        <div className="skeleton h-72 w-full" />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      {/* Breadcrumb + title */}
      <div className="flex items-center gap-2 text-xs text-muted">
        <Link href="/" className="hover:text-text">
          Markets
        </Link>
        <span>/</span>
        <span>{market.category}</span>
      </div>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface-2 text-2xl">
            {market.icon}
          </span>
          <div>
            <h1 className="text-xl font-black text-text sm:text-2xl">{market.title}</h1>
            <p className="mt-0.5 text-sm text-muted">{market.question}</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted">
          <span className="font-mono">{formatCompactUSD(market.volume)} vol</span>
          <span className="font-mono">{market.traders.toLocaleString()} traders</span>
          <span className="rounded-md bg-surface-2 px-2 py-1 font-mono">
            closes {timeUntil(market.endsAt)}
          </span>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left: chart, outcomes, book, AI, tabs */}
        <div className="min-w-0 space-y-5">
          <div className="rounded-xl border border-border bg-surface p-4">
            <PriceChart slug={market.slug} endPrice={market.outcomes[0].price} height={360} />
          </div>

          {/* Outcome strip */}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {market.outcomes.map((o) => (
              <div
                key={o.id}
                className="flex items-center justify-between rounded-xl border border-border bg-surface px-3 py-2.5"
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-text">
                  <span>{o.emoji}</span>
                  {o.label}
                </span>
                <span className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] text-muted-2">
                    {multiplier(o.price)}
                  </span>
                  <span className={cn("font-mono text-lg font-black", toneClass(o.tone))}>
                    {pct(o.price)}
                  </span>
                </span>
              </div>
            ))}
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <OrderBook market={market} />
            <AIForecastPanel market={market} />
          </div>

          <MarketTabs market={market} />
        </div>

        {/* Right: sticky trade panel */}
        <div className="flex flex-col gap-5 lg:sticky lg:top-28 lg:self-start">
          <TradePanel market={market} />
          <DecisionSignalPanel market={market} />
        </div>
      </div>
    </main>
  );
}
