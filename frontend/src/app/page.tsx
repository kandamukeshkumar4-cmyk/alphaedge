"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  MARKETS,
  marketsByCategory,
  trendingRows,
  topMoverRows,
  newRows,
  highestVolumeRows,
  type Market,
} from "@/lib/mock-data";
import { HeroFeature } from "@/components/HeroFeature";
import { FeaturedMarketCard } from "@/components/FeaturedMarketCard";
import { DiscoveryRail } from "@/components/DiscoveryRail";
import { LiveTicker } from "@/components/LiveTicker";
import { MotionReveal } from "@/components/MotionReveal";
import { PromoCard } from "@/components/RightRailExtras";
import { OnboardingModal } from "@/components/OnboardingModal";
import { MarketSearch } from "@/components/MarketSearch";
import { useOnboarding } from "@/hooks/useOnboarding";
import { fetchMarkets, type MarketFilterParams } from "@/lib/alphaedge-api";
import type { LeaderboardEntry } from "@/lib/leaderboard-api";
import { fetchLeaderboard } from "@/lib/leaderboard-api";
import { cn } from "@/lib/cn";

function formatPnl(pnl: number) {
  const sign = pnl >= 0 ? "+" : "";
  return `${sign}$${Math.abs(pnl).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function LeaderboardSidebar({ entries }: { entries: LeaderboardEntry[] }) {
  if (!entries.length) return null;
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <h3 className="mb-3 text-sm font-black text-text">Top Traders</h3>
      <ol className="space-y-2">
        {entries.slice(0, 5).map((e) => (
          <li key={e.rank} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2 min-w-0">
              <span className="w-4 shrink-0 text-right text-xs font-mono text-muted">
                {e.rank}
              </span>
              <span className="truncate text-xs font-semibold text-text">{e.username}</span>
            </span>
            <span
              className={cn(
                "shrink-0 text-xs font-mono font-bold",
                e.realized_pnl >= 0 ? "text-emerald-400" : "text-red-400",
              )}
            >
              {formatPnl(e.realized_pnl)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function Home() {
  const featured = MARKETS.slice(0, 4);
  const groups = marketsByCategory();
  const { shouldShow, markDone } = useOnboarding();

  const [filteredMarkets, setFilteredMarkets] = useState<Market[]>(MARKETS);
  const [loading, setLoading] = useState(false);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [activeParams, setActiveParams] = useState<MarketFilterParams>({});

  const loadMarkets = useCallback(async (params: MarketFilterParams) => {
    setLoading(true);
    try {
      const result = await fetchMarkets(params);
      setFilteredMarkets(result);
    } catch {
      setFilteredMarkets(MARKETS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMarkets({});
    fetchLeaderboard()
      .then(setLeaderboard)
      .catch(() => {});
  }, [loadMarkets]);

  function handleFilterChange(params: MarketFilterParams) {
    setActiveParams(params);
    void loadMarkets(params);
  }

  const isFiltered =
    !!activeParams.category || !!activeParams.q || (activeParams.sort && activeParams.sort !== "volume");

  const displayGroups = isFiltered
    ? filteredMarkets.length > 0
      ? [{ category: "Results", markets: filteredMarkets }]
      : []
    : groups;

  return (
    <>
      {shouldShow && <OnboardingModal onDone={markDone} />}

      <main className="mx-auto max-w-[1440px] px-4 py-5 sm:px-5">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_354px]">
          <div className="min-w-0 space-y-5">
            <MotionReveal>
              <HeroFeature markets={featured} />
            </MotionReveal>

            <MarketSearch onChange={handleFilterChange} loading={loading} />

            {displayGroups.length === 0 && isFiltered && (
              <p className="py-8 text-center text-sm text-muted">
                No markets match your search.
              </p>
            )}

            {displayGroups.map((group, gi) => (
              <section key={group.category}>
                <div className="mb-3 flex items-end justify-between gap-3">
                  <h2 className="text-lg font-black tracking-tight text-text">
                    {group.category}
                  </h2>
                  {!isFiltered && (
                    <Link
                      href={`/markets?cat=${group.category}`}
                      className="rounded-md border border-border px-3 py-1.5 text-xs font-black text-muted transition hover:border-border-light hover:text-text"
                    >
                      See all
                    </Link>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
                  {group.markets.map((market, mi) => (
                    <MotionReveal key={market.slug} delay={Math.min(0.04 * mi + 0.02 * gi, 0.2)}>
                      <FeaturedMarketCard market={market} />
                    </MotionReveal>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <aside className="space-y-4 lg:sticky lg:top-[124px] lg:self-start">
            <LeaderboardSidebar entries={leaderboard} />
            <DiscoveryRail title="Trending" rows={trendingRows()} />
            <DiscoveryRail title="Top movers" rows={topMoverRows()} />
            <PromoCard />
            <DiscoveryRail title="New" rows={newRows()} />
            <DiscoveryRail title="Highest volume" rows={highestVolumeRows()} />
            <LiveTicker />
          </aside>
        </div>
      </main>
    </>
  );
}
