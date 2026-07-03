"use client";

import { useEffect, useMemo, useState } from "react";
import { QuestHero } from "@/components/quest/QuestHero";
import { QuestLeftRail } from "@/components/quest/QuestLeftRail";
import { QuestAgentPanel } from "@/components/quest/QuestAgentPanel";
import { QuestTicker } from "@/components/quest/QuestTicker";
import {
  QuestMarketCard,
  QuestMarketCardSkeleton,
} from "@/components/quest/QuestMarketCard";
import { QuestFeed } from "@/components/quest/QuestFeed";
import { collectPrioritySlugs, LivePricesProvider } from "@/context/live-prices";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { MARKETS, type Category, type Market } from "@/lib/mock-data";
import { DemoChip } from "@/components/quest/DemoChip";

const FILTERS: Array<{ id: "all" | Category; label: string }> = [
  { id: "all", label: "All" },
  { id: "Sports", label: "Sports" },
  { id: "Politics", label: "Politics" },
  { id: "Crypto", label: "Crypto" },
  { id: "Culture", label: "Culture" },
  { id: "Economics", label: "Economics" },
];

export function QuestDiscover() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [demo, setDemo] = useState(false);
  const [filter, setFilter] = useState<"all" | Category>("all");
  const [tab, setTab] = useState<"markets" | "feed">("markets");

  useEffect(() => {
    let dead = false;
    fetchMarkets({})
      .then((result) => {
        if (dead) return;
        if (result.length > 0) {
          setMarkets(result);
        } else {
          setMarkets(MARKETS);
          setDemo(true);
        }
      })
      .catch(() => {
        if (dead) return;
        // Backend down → explorable demo catalog instead of an empty page.
        setMarkets(MARKETS);
        setDemo(true);
      })
      .finally(() => {
        if (!dead) setLoading(false);
      });
    return () => {
      dead = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const list =
      filter === "all" ? markets : markets.filter((m) => m.category === filter);
    return [...list].sort((a, b) => b.volume - a.volume);
  }, [markets, filter]);

  const trending = useMemo(
    () => [...markets].sort((a, b) => b.trendDelta - a.trendDelta).slice(0, 5),
    [markets],
  );

  const prioritySlugs = useMemo(
    () => collectPrioritySlugs(filtered.slice(0, 24), trending),
    [filtered, trending],
  );

  return (
    <LivePricesProvider markets={markets} prioritySlugs={prioritySlugs}>
      <div className="mx-auto flex max-w-[1600px] flex-col gap-3 px-3 py-3 pb-12 sm:px-4 lg:flex-row">
        <QuestLeftRail trending={trending} />

        <main className="min-w-0 flex-1">
          <QuestHero />

          <div className="no-scrollbar mt-3 flex items-center gap-1 overflow-x-auto border-b border-border pb-px">
            {(
              [
                { id: "markets", label: "Markets" },
                { id: "feed", label: "Feed" },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "shrink-0 rounded-t-md px-3 py-1.5 text-[13px] font-semibold transition",
                  tab === t.id
                    ? "border-b-2 border-accent-bright text-text"
                    : "text-muted hover:text-text",
                )}
              >
                {t.label}
              </button>
            ))}
            {tab === "markets" && (
              <div className="ml-3 flex gap-1 border-l border-border pl-3">
                {FILTERS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFilter(f.id)}
                    className={cn(
                      "shrink-0 rounded-pill border px-2.5 py-0.5 text-[11px] font-semibold transition",
                      filter === f.id
                        ? "border-accent-bright text-accent-bright"
                        : "border-transparent text-muted hover:text-text",
                    )}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {tab === "feed" && <QuestFeed />}

          {tab === "markets" && demo && (
            <p className="mt-4 flex items-center gap-2 rounded-lg border border-secondary/30 bg-secondary-dim px-4 py-2.5 text-xs text-secondary">
              <DemoChip />
              Showing sample markets — start the backend (`docker compose up`) for live
              Kalshi &amp; Polymarket prices.
            </p>
          )}

          {tab === "markets" &&
          (loading && filtered.length === 0 ? (
            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {Array.from({ length: 12 }, (_, i) => (
                <QuestMarketCardSkeleton key={i} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <p className="mt-8 py-12 text-center text-sm text-muted-2">
              No markets in this category yet.
            </p>
          ) : (
            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {filtered.slice(0, 32).map((market) => (
                <QuestMarketCard key={market.id} market={market} />
              ))}
            </div>
          ))}
        </main>

        <QuestAgentPanel />
      </div>
      <QuestTicker />
    </LivePricesProvider>
  );
}
