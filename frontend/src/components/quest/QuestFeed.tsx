"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { formatCompactUSD, type Market } from "@/lib/mock-data";
import { marketHref } from "@/lib/market-href";
import { cn } from "@/lib/cn";
import { useAtlasPanel } from "@/context/atlas-panel";

type FeedTab = "for-you" | "new" | "following";

type FeedItem = {
  id: string;
  author: string;
  stance: "bullish" | "bearish";
  market: Market;
  rationale: string;
  age: string;
};

function buildFeed(markets: Market[]): FeedItem[] {
  const authors = ["ScottyNooo", "edge_walker", "atlas_clone", "paper_whale", "kalshi_scout"];
  return markets.slice(0, 12).map((m, i) => {
    const yes = m.outcomes[0]?.price ?? 0.5;
    return {
      id: `${m.slug}-${i}`,
      author: authors[i % authors.length],
      stance: yes >= 0.5 ? "bullish" : "bearish",
      market: m,
      rationale:
        yes >= 0.5
          ? `Paper edge on YES at ${Math.round(yes * 100)}¢ — volume ${formatCompactUSD(m.volume)}.`
          : `Fading YES at ${Math.round(yes * 100)}¢ — watching for mean reversion.`,
      age: i < 3 ? `${i + 1}h ago` : `${i + 2}d ago`,
    };
  });
}

export function QuestFeed({ markets }: { markets: Market[] }) {
  const [tab, setTab] = useState<FeedTab>("for-you");
  const { openPanel } = useAtlasPanel();
  const items = useMemo(() => buildFeed(markets), [markets]);

  const filtered =
    tab === "following"
      ? items.filter((_, i) => i % 2 === 0)
      : tab === "new"
        ? [...items].reverse()
        : items;

  return (
    <div>
      <div className="mb-4 flex items-center gap-1 border-b border-border">
        {(
          [
            ["for-you", "For You"],
            ["new", "New"],
            ["following", "Following"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "relative px-4 py-2.5 text-sm font-semibold transition",
              tab === id ? "text-text" : "text-muted hover:text-text",
            )}
          >
            {label}
            {tab === id ? (
              <motion.span
                layoutId="feed-tab"
                className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-primary"
              />
            ) : null}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="py-16 text-center text-sm text-muted-2">No quests in this feed yet.</p>
      ) : (
        <ul className="space-y-2">
          {filtered.map((item, i) => {
            const yes = item.market.outcomes[0]?.price ?? 0.5;
            const no = 1 - yes;
            const yesC = Math.round(yes * 100);
            const noC = Math.round(no * 100);
            return (
              <motion.li
                key={item.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.03, 0.2), duration: 0.2 }}
                className="rounded-[10px] border border-border bg-surface px-3.5 py-3 transition hover:border-primary/30"
              >
                <div className="flex items-start gap-2.5">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-border bg-surface-2 text-[10px] font-bold text-primary">
                    {item.author.slice(0, 2).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                      <p className="text-[13px] leading-snug text-text">
                        <span className="font-bold">{item.author}</span>{" "}
                        <span className="text-muted">is</span>{" "}
                        <span
                          className={
                            item.stance === "bullish"
                              ? "font-semibold text-primary"
                              : "font-semibold text-danger"
                          }
                        >
                          {item.stance === "bullish" ? "Long" : "Short"}
                        </span>{" "}
                        <span className="text-muted">on</span>{" "}
                        <Link
                          href={marketHref(item.market.slug)}
                          className="font-semibold text-text underline-offset-2 hover:text-primary hover:underline"
                        >
                          {item.market.title}
                        </Link>
                      </p>
                      <span className="text-[10px] text-muted-2">{item.age}</span>
                    </div>

                    <div className="mt-2.5 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                      <div className="flex min-w-0 items-center gap-2.5 rounded-lg border border-border/80 bg-bg/50 px-2.5 py-2">
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-surface-2 text-base">
                          {item.market.icon || "◆"}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-[12px] font-semibold text-text">
                              {item.market.title}
                            </p>
                            <span className="shrink-0 font-mono text-[11px] font-bold tabular-nums text-primary">
                              {yesC}%
                            </span>
                          </div>
                          <div className="mt-1.5 flex h-1 overflow-hidden rounded-full bg-surface-3">
                            <div className="h-full bg-primary" style={{ width: `${yesC}%` }} />
                            <div className="h-full bg-danger" style={{ width: `${noC}%` }} />
                          </div>
                          <div className="mt-1 flex justify-between font-mono text-[9px] text-muted-2">
                            <span>YES {yesC}¢</span>
                            <span>NO {noC}¢</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-stretch gap-1.5 sm:flex-col">
                        <Link
                          href={`/trade?slug=${encodeURIComponent(item.market.slug)}`}
                          className="flex flex-1 items-center justify-center rounded-lg bg-primary px-3.5 py-1.5 text-center text-[11px] font-bold text-bg transition hover:brightness-110"
                        >
                          Analyze
                        </Link>
                        <button
                          type="button"
                          onClick={() =>
                            openPanel({
                              mode: "analyze",
                              marketSlug: item.market.slug,
                              marketTitle: item.market.title,
                              seedPrompt: `Analyze ${item.market.title}. Stance was ${item.stance}.`,
                            })
                          }
                          className="flex flex-1 items-center justify-center rounded-lg border border-border bg-surface-2 px-3.5 py-1.5 text-[11px] font-bold text-muted transition hover:border-primary/40 hover:text-primary"
                        >
                          AI analysis
                        </button>
                      </div>
                    </div>

                    <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-muted">
                      {item.rationale}
                    </p>
                  </div>
                </div>
              </motion.li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
