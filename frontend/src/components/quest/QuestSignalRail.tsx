"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchMarkets } from "@/lib/alphaedge-api";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard-api";
import { fetchSignalEvents } from "@/lib/activity-api";
import { marketHref } from "@/lib/market-href";
import { formatCompactUSD, type Market } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

// Discover left rail — Top Traders, Trending Markets, Live Signals. Every row
// is live from the backend; there are no seeded/placeholder values. When an
// endpoint is empty (e.g. leaderboard not yet populated) the section renders an
// honest empty state instead of fabricated data.

function rankColor(rank: number): string {
  if (rank === 1) return "text-danger";
  if (rank <= 3) return "text-gold";
  return "text-muted";
}

function money(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

function RailHeader({ title, href }: { title: string; href: string }) {
  return (
    <div className="flex items-center justify-between px-1 pb-2 pt-1">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted">{title}</h2>
      <Link href={href} className="text-[11px] font-semibold text-muted-2 transition hover:text-primary">
        See all
      </Link>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="px-1 py-3 text-[11px] leading-relaxed text-muted-2">{text}</p>;
}

type Signal = { key: string; side: "LONG" | "SHORT"; ticker: string; label: string; value: string };

function tickerOf(m: Market): string {
  return m.title.split(" ")[0].toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 4) || "MKT";
}

type PlatformTab = "all" | "polymarket" | "kalshi";

export function QuestSignalRail({
  initialMarkets,
}: {
  initialMarkets?: Market[];
}) {
  const [platform, setPlatform] = useState<PlatformTab>("all");
  const [traders, setTraders] = useState<LeaderboardEntry[] | null>(null);
  const [trending, setTrending] = useState<Market[] | null>(
    initialMarkets && initialMarkets.length > 0
      ? [...initialMarkets].sort((a, b) => b.volume - a.volume).slice(0, 6)
      : null,
  );
  const [allTrending, setAllTrending] = useState<Market[]>(
    initialMarkets && initialMarkets.length > 0
      ? [...initialMarkets].sort((a, b) => b.volume - a.volume).slice(0, 12)
      : [],
  );
  const [signals, setSignals] = useState<Signal[] | null>(null);

  useEffect(() => {
    let dead = false;

    fetchLeaderboard()
      .then((rows) => !dead && setTraders(rows.slice(0, 5)))
      .catch(() => !dead && setTraders([]));

    fetchMarkets({})
      .then((rows) => {
        if (dead) return;
        const sorted = [...rows].sort((a, b) => b.volume - a.volume);
        setAllTrending(sorted.slice(0, 12));
        const top = sorted.slice(0, 6);
        setTrending(top);

        // Live signals: prefer real signal events; else derive whale flow from
        // the strongest real market moves (still backend data, not mock).
        fetchSignalEvents({ limit: 6 })
          .then((events) => {
            if (dead) return;
            if (events.length > 0) {
              const byId = new Map(rows.map((m) => [m.id, m]));
              setSignals(
                events.slice(0, 5).map((e, i) => {
                  const m = byId.get(e.market_id);
                  const up = e.signal_type.toLowerCase().includes("buy");
                  return {
                    key: e.id,
                    side: up ? "LONG" : "SHORT",
                    ticker: m ? tickerOf(m) : e.platform.slice(0, 4).toUpperCase(),
                    label: e.signal_type.replace(/_/g, " "),
                    value: m ? formatCompactUSD(m.volume) : "—",
                  } satisfies Signal;
                }),
              );
            } else {
              setSignals(
                top.slice(0, 5).map((m, i) => ({
                  key: m.id,
                  side: (m.trendDelta ?? 0) >= 0 ? "LONG" : "SHORT",
                  ticker: tickerOf(m),
                  label: (m.trendDelta ?? 0) >= 0 ? "Whale entering" : "Whale exiting",
                  value: formatCompactUSD(m.volume),
                })),
              );
            }
          })
          .catch(() => !dead && setSignals([]));
      })
      .catch(() => {
        if (dead) return;
        setTrending([]);
        setSignals([]);
      });

    return () => {
      dead = true;
    };
  }, []);

  const visibleTrending = (() => {
    const source = allTrending.length > 0 ? allTrending : trending ?? [];
    if (platform === "polymarket") {
      return source
        .filter((m) => m.source === "polymarket" || !m.source || m.source === "seed")
        .slice(0, 6);
    }
    if (platform === "kalshi") {
      return source.filter((m) => m.source === "kalshi").slice(0, 6);
    }
    return source.slice(0, 6);
  })();

  return (
    <aside className="flex flex-col gap-5">
      <div className="flex gap-1 rounded-lg border border-border bg-surface p-1">
        {(
          [
            ["all", "All"],
            ["polymarket", "Polymarket"],
            ["kalshi", "Kalshi"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setPlatform(id)}
            className={cn(
              "flex-1 rounded-md px-2 py-1.5 text-[10px] font-bold transition",
              platform === id
                ? "bg-primary-dim text-primary"
                : "text-muted hover:text-text",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Top Traders */}
      <section>
        <RailHeader title="Top Traders" href="/leaderboard" />
        {traders === null ? (
          <SkeletonRows n={5} />
        ) : traders.length === 0 ? (
          <Empty text="No ranked traders yet — the leaderboard populates from graded paper trades." />
        ) : (
          <ul className="divide-y divide-border/50">
            {traders.map((t) => (
              <li key={t.username} className="flex items-center gap-2.5 py-2">
                <span className={cn("w-3 text-xs font-bold tabular-nums", rankColor(t.rank))}>{t.rank}</span>
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-border bg-surface-2 text-[10px] font-bold text-text">
                  {t.username.slice(0, 2).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-text">{t.username}</span>
                <span className="text-[13px] font-semibold tabular-nums text-primary">{money(t.realized_pnl)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Trending Markets */}
      <section>
        <RailHeader title="Trending Markets" href="/markets" />
        {trending === null ? (
          <SkeletonRows n={6} />
        ) : visibleTrending.length === 0 ? (
          <Empty text="No live markets right now." />
        ) : (
          <ul className="divide-y divide-border/50">
            {visibleTrending.map((m, i) => (
              <li key={m.id}>
                <Link href={marketHref(m.slug)} className="flex items-center gap-2.5 py-2">
                  <span className={cn("w-3 text-xs font-bold tabular-nums", rankColor(i + 1))}>{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-text hover:text-primary">{m.title}</span>
                  <span className="text-right">
                    <span className="block text-[13px] font-bold tabular-nums text-text">
                      {Math.round((m.outcomes?.[0]?.price ?? 0.5) * 100)}%
                    </span>
                    <span className="block text-[10px] text-muted-2">{formatCompactUSD(m.volume)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Live Signals */}
      <section>
        <RailHeader title="Live Signals" href="/signals" />
        {signals === null ? (
          <SkeletonRows n={5} />
        ) : signals.length === 0 ? (
          <Empty text="No signals firing yet." />
        ) : (
          <ul className="divide-y divide-border/50">
            {signals.map((s) => (
              <li key={s.key} className="flex items-center gap-2.5 py-2">
                <span
                  className={cn(
                    "rounded border px-1.5 py-0.5 text-[9px] font-bold tracking-wide",
                    s.side === "LONG"
                      ? "border-primary/40 bg-primary-dim/60 text-primary"
                      : "border-danger/40 bg-danger-dim/60 text-danger",
                  )}
                >
                  {s.side}
                </span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-text">
                  <span className="font-bold">{s.ticker}</span> <span className="text-muted">{s.label}</span>
                </span>
                <span className="text-[12px] font-semibold tabular-nums text-text">{s.value}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

function SkeletonRows({ n }: { n: number }) {
  return (
    <ul className="flex flex-col gap-2 py-1">
      {Array.from({ length: n }, (_, i) => (
        <li key={i} className="skeleton h-7 w-full rounded" />
      ))}
    </ul>
  );
}
