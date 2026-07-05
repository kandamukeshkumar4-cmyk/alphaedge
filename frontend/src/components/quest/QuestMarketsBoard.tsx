"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { QuestHero } from "@/components/quest/QuestHero";
import {
  QuestMarketCard,
  QuestMarketCardSkeleton,
} from "@/components/quest/QuestMarketCard";
import { collectPrioritySlugs, LivePricesProvider } from "@/context/live-prices";
import { fetchMarkets } from "@/lib/alphaedge-api";
import {
  KALSHI_TOPICS,
  filterByTopic,
  topicToApiCategory,
  type KalshiTopicId,
} from "@/lib/kalshi-topics";
import { cn } from "@/lib/cn";
import { MARKETS, type Market } from "@/lib/mock-data";
import { DemoChip } from "@/components/quest/DemoChip";

function parseTopic(raw: string | null): KalshiTopicId {
  return KALSHI_TOPICS.some((t) => t.id === raw) ? (raw as KalshiTopicId) : "trending";
}

// /markets board in the Quest design system: topic pills + live card grid.
// Replaces the old Kalshi row-list design.
export function QuestMarketsBoard() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const topic = parseTopic(searchParams.get("topic"));
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();

  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [demo, setDemo] = useState(false);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    try {
      const apiCat = topicToApiCategory(topic);
      const result = await fetchMarkets(apiCat ? { category: apiCat } : {});
      if (requestId !== requestIdRef.current) return;
      if (result.length > 0) {
        setMarkets(result);
        setDemo(false);
      } else {
        setMarkets(MARKETS);
        setDemo(true);
      }
    } catch {
      if (requestId !== requestIdRef.current) return;
      // Backend down → explorable demo catalog instead of an empty board.
      setMarkets(MARKETS);
      setDemo(true);
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [topic]);

  useEffect(() => {
    void load();
  }, [load]);

  const goTopic = useCallback(
    (id: KalshiTopicId) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id === "trending") params.delete("topic");
      else params.set("topic", id);
      const qs = params.toString();
      router.push(qs ? `/markets?${qs}` : "/markets");
    },
    [router, searchParams],
  );

  const filtered = useMemo(() => {
    let list = filterByTopic(markets, topic);
    if (query) {
      list = list.filter(
        (m) =>
          m.title.toLowerCase().includes(query) ||
          m.question.toLowerCase().includes(query) ||
          m.slug.toLowerCase().includes(query),
      );
    }
    return [...list].sort((a, b) => b.volume - a.volume);
  }, [markets, topic, query]);

  const prioritySlugs = useMemo(
    () => collectPrioritySlugs(filtered.slice(0, 24)),
    [filtered],
  );

  return (
    <LivePricesProvider markets={markets} prioritySlugs={prioritySlugs}>
      <div className="mx-auto max-w-[1400px] px-4 py-4 sm:px-6">
        {topic === "trending" && !query ? <QuestHero /> : null}

        <div className="no-scrollbar mt-4 flex gap-1 overflow-x-auto">
          {KALSHI_TOPICS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => goTopic(t.id)}
              className={cn(
                "shrink-0 rounded-pill px-4 py-1.5 text-sm font-semibold transition",
                topic === t.id
                  ? "bg-accent-bright text-bg"
                  : "bg-surface text-muted hover:text-text",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {demo && (
          <p className="mt-4 flex items-center gap-2 rounded-lg border border-secondary/30 bg-secondary-dim px-4 py-2.5 text-xs text-secondary">
            <DemoChip />
            Showing sample markets — start the backend for live Kalshi &amp; Polymarket
            prices.
          </p>
        )}

        {loading && filtered.length === 0 ? (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 12 }, (_, i) => (
              <QuestMarketCardSkeleton key={i} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p className="mt-8 py-12 text-center text-sm text-muted-2">
            No markets in this topic{query ? ` matching “${query}”` : ""}.
          </p>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((market) => (
              <QuestMarketCard key={market.id} market={market} />
            ))}
          </div>
        )}
      </div>
    </LivePricesProvider>
  );
}
