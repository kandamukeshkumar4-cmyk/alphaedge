"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { QuestArenaHero } from "@/components/quest/QuestArenaHero";
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
import { type Market } from "@/lib/mock-data";

function parseTopic(raw: string | null): KalshiTopicId {
  return KALSHI_TOPICS.some((t) => t.id === raw) ? (raw as KalshiTopicId) : "trending";
}

// /markets board in the Quest design system: topic pills + live card grid.
// Replaces the old Kalshi row-list design.
export function QuestMarketsBoard({
  showHero = true,
  initialMarkets,
}: {
  showHero?: boolean;
  initialMarkets?: Market[];
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const topic = parseTopic(searchParams.get("topic"));
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();

  const [markets, setMarkets] = useState<Market[]>(initialMarkets ?? []);
  const [loading, setLoading] = useState(!initialMarkets || initialMarkets.length === 0);
  const [error, setError] = useState(false);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(false);
    try {
      const apiCat = topicToApiCategory(topic);
      const result = await fetchMarkets(apiCat ? { category: apiCat } : {});
      if (requestId !== requestIdRef.current) return;
      // Live data only — no mock fallback. Empty/error render honest states.
      setMarkets(result);
    } catch {
      if (requestId !== requestIdRef.current) return;
      setMarkets((prev) => (prev.length > 0 ? prev : []));
      setError(true);
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
        {showHero && topic === "trending" && !query ? <QuestArenaHero /> : null}

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

        {topic !== "trending" && !query ? (
          <div className="mt-3">
            <Link
              href={`/categories/${encodeURIComponent(topic)}`}
              className="inline-flex items-center gap-1.5 rounded-pill border border-accent/40 bg-accent/10 px-3.5 py-1.5 text-xs font-bold text-accent transition hover:border-accent hover:bg-accent/15"
            >
              {KALSHI_TOPICS.find((t) => t.id === topic)?.label ?? topic} intelligence dashboard →
            </Link>
          </div>
        ) : null}

        {error && (
          <p className="mt-4 flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-dim px-4 py-2.5 text-xs text-danger">
            Couldn&rsquo;t refresh markets — showing last loaded data. Retrying on next load.
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
