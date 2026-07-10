"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { QuestArenaHero } from "@/components/quest/QuestArenaHero";
import { QuestFeed } from "@/components/quest/QuestFeed";
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

const INTELLIGENCE_LINKS = [
  { href: "/opportunities", label: "Opportunities", blurb: "Biggest model-vs-market edges" },
  { href: "/markets", label: "Desk", blurb: "Per-market intelligence panel" },
  { href: "/clones", label: "Clones", blurb: "Paper agent clones" },
  { href: "/backtest", label: "Backtest", blurb: "Walk-forward record & replay" },
  { href: "/track-record", label: "Track record", blurb: "Analyst scoreboard" },
  { href: "/smart-money", label: "Smart money", blurb: "Whale flow & concentration" },
  { href: "/arb", label: "Arb desk", blurb: "Cross-venue signal matches" },
  { href: "/feed", label: "Feed", blurb: "Live activity stream" },
  { href: "/leaderboard", label: "Leaderboard", blurb: "Paper P&L ranks" },
] as const;

type MainTab = "markets" | "feed";

function parseTopic(raw: string | null): KalshiTopicId {
  return KALSHI_TOPICS.some((t) => t.id === raw) ? (raw as KalshiTopicId) : "trending";
}

export function QuestDiscoverShell({ initialMarkets }: { initialMarkets?: Market[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const topic = parseTopic(searchParams.get("topic"));
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();
  const mainTab = (searchParams.get("tab") === "feed" ? "feed" : "markets") as MainTab;

  const [markets, setMarkets] = useState<Market[]>(initialMarkets ?? []);
  const [loading, setLoading] = useState(!initialMarkets || initialMarkets.length === 0);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const apiCat = topicToApiCategory(topic);
      const result = await fetchMarkets(apiCat ? { category: apiCat } : {});
      setMarkets(result);
    } catch {
      setMarkets((prev) => (prev.length > 0 ? prev : []));
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [topic]);

  useEffect(() => {
    void load();
  }, [load]);

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (!value) params.delete(key);
      else params.set(key, value);
      const qs = params.toString();
      router.push(qs ? `/?${qs}` : "/");
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
      <div className="min-w-0">
        <QuestArenaHero />

        <section className="mt-5 rounded-2xl border border-border bg-surface px-4 py-4">
          <h2 className="text-sm font-black uppercase tracking-[0.08em] text-muted">
            Intelligence
          </h2>
          <p className="mt-1 text-xs text-muted">
            Report Tier-1 surfaces — paper simulation only.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {INTELLIGENCE_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-xl border border-border bg-bg/40 px-3 py-2 transition hover:border-primary/50 hover:text-primary"
              >
                <span className="block text-sm font-bold text-text">{link.label}</span>
                <span className="block text-[11px] text-muted">{link.blurb}</span>
              </Link>
            ))}
          </div>
        </section>

        <div className="mt-5 flex items-center gap-1 border-b border-border">
          {(
            [
              ["markets", "Markets"],
              ["feed", "Feed"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setParam("tab", id === "markets" ? null : id)}
              className={cn(
                "relative px-4 py-2.5 text-sm font-bold transition",
                mainTab === id ? "text-text" : "text-muted hover:text-text",
              )}
            >
              {label}
              {mainTab === id ? (
                <motion.span
                  layoutId="discover-main-tab"
                  className="absolute inset-x-1 bottom-0 h-0.5 rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.6)]"
                />
              ) : null}
            </button>
          ))}
        </div>

        {mainTab === "markets" ? (
          <>
            <div className="no-scrollbar mt-3 flex gap-1.5 overflow-x-auto pb-1">
              {KALSHI_TOPICS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setParam("topic", t.id === "trending" ? null : t.id)}
                  className={cn(
                    "shrink-0 rounded-full border px-3.5 py-1.5 text-xs font-bold transition",
                    topic === t.id
                      ? "border-primary/60 bg-primary-dim text-primary"
                      : "border-border bg-surface text-muted hover:border-border-light hover:text-text",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {error ? (
              <p className="mt-4 rounded-lg border border-danger/30 bg-danger-dim px-4 py-2.5 text-xs text-danger">
                Couldn&rsquo;t refresh markets — showing last loaded data.
              </p>
            ) : null}

            {loading && filtered.length === 0 ? (
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {Array.from({ length: 12 }, (_, i) => (
                  <QuestMarketCardSkeleton key={i} />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <p className="mt-8 py-12 text-center text-sm text-muted-2">
                No markets in this topic{query ? ` matching “${query}”` : ""}.
              </p>
            ) : (
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {filtered.map((market, i) => (
                  <motion.div
                    key={market.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(i * 0.03, 0.3), duration: 0.2 }}
                  >
                    <QuestMarketCard market={market} />
                  </motion.div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="mt-4">
            <QuestFeed markets={markets} />
          </div>
        )}
      </div>
    </LivePricesProvider>
  );
}
