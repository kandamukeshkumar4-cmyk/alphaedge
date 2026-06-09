import Link from "next/link";
import {
  MARKETS,
  marketsByCategory,
  trendingRows,
  topMoverRows,
  newRows,
  highestVolumeRows,
} from "@/lib/mock-data";
import { HeroFeature } from "@/components/HeroFeature";
import { FeaturedMarketCard } from "@/components/FeaturedMarketCard";
import { DiscoveryRail } from "@/components/DiscoveryRail";
import { LiveTicker } from "@/components/LiveTicker";
import { MotionReveal } from "@/components/MotionReveal";
import { PromoCard } from "@/components/RightRailExtras";

export default function Home() {
  const featured = MARKETS.slice(0, 4);
  const groups = marketsByCategory();

  return (
    <main className="mx-auto max-w-[1440px] px-4 py-5 sm:px-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_354px]">
        <div className="min-w-0 space-y-5">
          <MotionReveal>
            <HeroFeature markets={featured} />
          </MotionReveal>

          {groups.map((group, gi) => (
            <section key={group.category}>
              <div className="mb-3 flex items-end justify-between gap-3">
                <h2 className="text-lg font-black tracking-tight text-text">
                  {group.category}
                </h2>
                <Link
                  href={`/markets?cat=${group.category}`}
                  className="rounded-md border border-border px-3 py-1.5 text-xs font-black text-muted transition hover:border-border-light hover:text-text"
                >
                  See all
                </Link>
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
          <DiscoveryRail title="Trending" rows={trendingRows()} />
          <DiscoveryRail title="Top movers" rows={topMoverRows()} />
          <PromoCard />
          <DiscoveryRail title="New" rows={newRows()} />
          <DiscoveryRail title="Highest volume" rows={highestVolumeRows()} />
          <LiveTicker />
        </aside>
      </div>
    </main>
  );
}
