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
import { MarketCard } from "@/components/MarketCard";
import { DiscoveryRail } from "@/components/DiscoveryRail";
import { LiveTicker } from "@/components/LiveTicker";
import { OnboardingBanner } from "@/components/OnboardingBanner";
import { MotionReveal } from "@/components/MotionReveal";
import { PromoCard, CategoryBanners, CustomizeView } from "@/components/RightRailExtras";

export default function Home() {
  const featured = MARKETS.slice(0, 4);
  const groups = marketsByCategory();

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* Center column */}
        <div className="min-w-0 space-y-6">
          <MotionReveal>
            <HeroFeature markets={featured} />
          </MotionReveal>

          <MotionReveal delay={0.05}>
            <OnboardingBanner />
          </MotionReveal>

          {groups.map((group, gi) => (
            <section key={group.category}>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-black text-text">
                  {group.category}
                </h2>
                <Link
                  href={`/markets?cat=${group.category}`}
                  className="text-sm font-semibold text-accent hover:underline"
                >
                  See all ›
                </Link>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
                {group.markets.map((market, mi) => (
                  <MotionReveal key={market.slug} delay={Math.min(0.04 * mi + 0.02 * gi, 0.2)}>
                    <MarketCard market={market} />
                  </MotionReveal>
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Right rail */}
        <aside className="space-y-4 lg:self-start">
          <PromoCard />
          <CategoryBanners />
          <CustomizeView />
          <DiscoveryRail title="Trending" rows={trendingRows()} />
          <DiscoveryRail title="Top movers" rows={topMoverRows()} />
          <LiveTicker />
          <DiscoveryRail title="New" rows={newRows()} />
          <DiscoveryRail title="Highest volume" rows={highestVolumeRows()} />
        </aside>
      </div>
    </main>
  );
}
