"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { KalshiDiscoveryRow, KalshiDiscoverySkeleton } from "@/components/KalshiDiscoveryRow";
import { KalshiHeroFeature } from "@/components/KalshiHeroFeature";
import { collectPrioritySlugs, LivePricesProvider } from "@/context/live-prices";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { pickHeroMarkets, pickHomeGridMarkets } from "@/lib/hero-market";
import {
  filterByTopic,
  topicToApiCategory,
  type KalshiTopicId,
} from "@/lib/kalshi-topics";
import type { Market } from "@/lib/mock-data";

function parseTopic(raw: string | null): KalshiTopicId {
  const ids: KalshiTopicId[] = [
    "trending",
    "sports",
    "politics",
    "crypto",
    "culture",
    "economics",
    "tech",
  ];
  return ids.includes(raw as KalshiTopicId) ? (raw as KalshiTopicId) : "trending";
}

export function KalshiMarketsFeed() {
  const searchParams = useSearchParams();
  const topic = parseTopic(searchParams.get("topic"));
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();

  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const apiCat = topicToApiCategory(topic);
      const result = await fetchMarkets(apiCat ? { category: apiCat } : {});
      if (requestId !== requestIdRef.current) return;
      setMarkets(result);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setMarkets([]);
      setError(err instanceof Error ? err.message : "Failed to load markets");
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [topic]);

  useEffect(() => {
    void load();
  }, [load]);

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

  const sportsKalshi = useMemo(() => {
    const sports = filterByTopic(markets, "sports");
    return pickHomeGridMarkets(sports.filter((m) => m.source === "kalshi"), 12);
  }, [markets]);

  const heroMarkets = useMemo(() => pickHeroMarkets(sportsKalshi), [sportsKalshi]);

  const showHero =
    (topic === "trending" || topic === "sports") && heroMarkets.length > 0 && !query;

  const prioritySlugs = useMemo(
    () => collectPrioritySlugs(heroMarkets, filtered.slice(0, 24)),
    [heroMarkets, filtered],
  );

  return (
    <LivePricesProvider markets={markets} prioritySlugs={prioritySlugs}>
      <div className="mx-auto max-w-[1280px] px-4 py-5 sm:px-6">
        {error ? (
          <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        ) : null}

        {showHero ? <KalshiHeroFeature markets={heroMarkets} /> : null}

        {loading && filtered.length === 0 ? (
          <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-[#0a0a0a]">
            {Array.from({ length: 10 }, (_, i) => (
              <KalshiDiscoverySkeleton key={i} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p className="mt-8 py-12 text-center text-sm text-white/50">
            No markets in this topic{query ? ` matching “${query}”` : ""}.
          </p>
        ) : (
          <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-[#0a0a0a]">
            {filtered.map((market) => (
              <KalshiDiscoveryRow key={market.id} market={market} />
            ))}
          </div>
        )}
      </div>
    </LivePricesProvider>
  );
}
