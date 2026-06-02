"use client";

import { useEffect, useState } from "react";
import {
  MARKETS,
  CATEGORIES,
  trendingRows,
  highestVolumeRows,
  type Category,
} from "@/lib/mock-data";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { marketCountLabel } from "@/lib/market-copy";
import { MarketCard } from "@/components/MarketCard";
import { DiscoveryRail } from "@/components/DiscoveryRail";
import { MotionReveal } from "@/components/MotionReveal";
import { cn } from "@/lib/cn";

type Filter = "All" | Category;

export default function MarketsPage() {
  const [filter, setFilter] = useState<Filter>("All");
  const [markets, setMarkets] = useState(MARKETS);

  useEffect(() => {
    const cat = new URLSearchParams(window.location.search).get("cat");
    if (cat && (CATEGORIES as string[]).includes(cat)) {
      setFilter(cat as Category);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchMarkets().then((apiMarkets) => {
      if (!cancelled) {
        setMarkets(apiMarkets);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered =
    filter === "All" ? markets : markets.filter((m) => m.category === filter);
  const categories = Array.from(new Set([...CATEGORIES, ...markets.map((m) => m.category)]));
  const filters: Filter[] = ["All", ...categories];

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-text">All markets</h1>
          <p className="mt-1 text-sm text-muted">
            {marketCountLabel(filtered.length)} · AI edge, live book, and proof metrics.
          </p>
        </div>
        <div className="rounded-lg border border-primary/25 bg-primary-dim px-4 py-2 text-sm">
          <span className="font-mono font-bold text-primary">$100,000</span>{" "}
          <span className="text-muted">paper bankroll</span>
        </div>
      </div>

      <div className="no-scrollbar mt-5 flex gap-2 overflow-x-auto">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm font-semibold transition",
              filter === f
                ? "border-primary bg-primary-dim text-primary"
                : "border-border text-muted hover:text-text",
            )}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid min-w-0 gap-3 sm:grid-cols-2">
          {filtered.map((m, i) => (
            <MotionReveal key={m.slug} delay={Math.min(i * 0.03, 0.2)}>
              <MarketCard market={m} />
            </MotionReveal>
          ))}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-28 lg:self-start">
          <DiscoveryRail title="Trending" rows={trendingRows()} />
          <DiscoveryRail title="Highest volume" rows={highestVolumeRows()} />
        </aside>
      </div>
    </main>
  );
}
