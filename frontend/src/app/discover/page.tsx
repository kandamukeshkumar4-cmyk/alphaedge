"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard-api";
import { MARKETS, trendingRows, type RankRow } from "@/lib/mock-data";
import { PageShell } from "@/components/ui/kit";

/*
 * Discover tab, QuestFlow-anatomy: Top Traders (ranked, teal values),
 * Trending Markets (rank-colored numbers, % + delta), Live Signals
 * (LONG/SHORT badges). All values are paper-simulation data.
 */

const DEMO_TRADERS: LeaderboardEntry[] = [
  { rank: 1, username: "quant_kestrel", realized_pnl: 1_530_000, total_trades: 412, win_rate: 0.71 },
  { rank: 2, username: "edge_seeker", realized_pnl: 1_090_000, total_trades: 388, win_rate: 0.66 },
  { rank: 3, username: "calibrated_ai", realized_pnl: 1_080_000, total_trades: 502, win_rate: 0.63 },
  { rank: 4, username: "polly_maxi", realized_pnl: 787_530, total_trades: 274, win_rate: 0.61 },
  { rank: 5, username: "delta_hunter", realized_pnl: 677_340, total_trades: 341, win_rate: 0.59 },
];

type LiveSignal = {
  rank: number;
  side: "LONG" | "SHORT";
  ticker: string;
  label: string;
  value: string;
  age: string;
};

// Deterministic demo signals derived from the mock catalog (paper only).
const LIVE_SIGNALS: LiveSignal[] = MARKETS.slice(0, 5).map((m, i) => ({
  rank: i + 1,
  side: m.trendDelta >= 0 ? "LONG" : "SHORT",
  ticker: m.title.split(" ")[0].toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 4) || "MKT",
  label: m.trendDelta >= 0 ? "Whale Entering" : "Whale Exiting",
  value: `$${((m.volume / 100) | 0) > 999 ? `${((m.volume / 100_000) | 0) / 10}k` : (m.volume / 100) | 0}`,
  age: `${(i + 1) * 3}m`,
}));

function rankColor(rank: number): string {
  if (rank === 1) return "text-danger";
  if (rank <= 3) return "text-gold";
  return "text-muted";
}

function money(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}k`;
  return `$${value.toFixed(0)}`;
}

function SectionTitle({ icon, title, href }: { icon: string; title: string; href?: string }) {
  return (
    <div className="flex items-center justify-between py-3">
      <h2 className="flex items-center gap-2.5 text-xl font-bold text-text">
        <span aria-hidden>{icon}</span>
        {title}
      </h2>
      {href ? (
        <Link href={href} className="text-muted transition hover:text-primary" aria-label={`See all ${title}`}>
          ›
        </Link>
      ) : null}
    </div>
  );
}

export default function DiscoverPage() {
  const [traders, setTraders] = useState<LeaderboardEntry[]>(DEMO_TRADERS);
  const trending = trendingRows();

  useEffect(() => {
    if (!API_BASE) return;
    fetchLeaderboard()
      .then((rows) => {
        if (rows.length > 0) setTraders(rows.slice(0, 5));
      })
      .catch(() => {});
  }, []);

  return (
    <PageShell width="narrow" className="pb-24">
      <SectionTitle icon="🖥️" title="Top Traders" href="/leaderboard" />
      <ul className="divide-y divide-border/60">
        {traders.map((t) => (
          <li key={t.username} className="flex items-center gap-4 py-3.5">
            <span className={cn("w-5 text-lg font-semibold tabular-nums", rankColor(t.rank))}>
              {t.rank}
            </span>
            <span className="grid h-11 w-11 place-items-center rounded-full border border-border bg-surface-2 text-xs font-bold text-text">
              {t.username.slice(0, 2).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1 truncate text-lg text-text">{t.username}</span>
            <span className="text-lg font-semibold tabular-nums text-primary">
              {money(t.realized_pnl)}
            </span>
          </li>
        ))}
      </ul>

      <div className="my-4 border-t border-dashed border-border" />

      <SectionTitle icon="🔺" title="Trending Markets" href="/markets" />
      <ul className="divide-y divide-border/60">
        {trending.slice(0, 5).map((row: RankRow, i: number) => (
          <li key={row.slug}>
            <Link href={`/markets/${row.slug}`} className="flex items-center gap-4 py-4">
              <span className={cn("w-5 text-lg font-semibold tabular-nums", rankColor(i + 1))}>
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-lg text-text">{row.title}</span>
              <span className="text-right">
                <span className="block text-2xl font-bold tabular-nums text-text">{row.value}</span>
                <span
                  className={cn(
                    "block text-sm font-semibold tabular-nums",
                    row.delta >= 0 ? "text-primary" : "text-danger",
                  )}
                >
                  {row.delta >= 0 ? "↗ +" : "↘ "}
                  {row.delta.toFixed(1)}%
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <div className="my-4 border-t border-dashed border-border" />

      <SectionTitle icon="📈" title="Live Signals" href="/signals" />
      <ul className="divide-y divide-border/60">
        {LIVE_SIGNALS.map((s) => (
          <li key={s.rank} className="flex items-center gap-4 py-4">
            <span className="w-5 text-lg tabular-nums text-muted">{s.rank}</span>
            <span
              className={cn(
                "rounded-md border px-2.5 py-1 text-xs font-bold tracking-wide",
                s.side === "LONG"
                  ? "border-primary/45 bg-primary-dim/60 text-primary"
                  : "border-danger/45 bg-danger-dim/60 text-danger",
              )}
            >
              {s.side}
            </span>
            <span className="min-w-0 flex-1 truncate text-lg text-text">
              <span className="font-bold">{s.ticker}</span>{" "}
              <span className="text-muted">{s.label}</span>
            </span>
            <span className="text-right">
              <span className="block text-lg font-bold tabular-nums text-text">{s.value}</span>
              <span className="block text-sm text-muted">{s.age}</span>
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-6 text-center text-xs text-muted-2">
        Paper simulation data — simulated funds only.
      </p>
    </PageShell>
  );
}
