"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard-api";
import { formatUSD } from "@/lib/mock-data";
import { PageHeader, PageShell, Panel, SegTabs, StatRow, StatTile } from "@/components/ui/kit";

/*
 * Trader Arena — QuestFlow-style leaderboard: an arena summary strip, a
 * podium for the top 3, sortable sub-tabs, and a ranked table with a
 * copy-trade (mirror) CTA on each row. Paper-trading only: "copy" links to
 * the Mirror simulator, never a live execution path.
 */

type ArenaSort = "pnl" | "active" | "winrate";

const SORT_OPTIONS = [
  { value: "pnl" as const, label: "Top P&L" },
  { value: "active" as const, label: "Most active" },
  { value: "winrate" as const, label: "Best win rate" },
];

// Demo fallback so the arena renders in demo mode (no API configured),
// mirroring the rest of the app's demo/fallback behavior.
const DEMO_LEADERBOARD: LeaderboardEntry[] = [
  { rank: 1, username: "quant_kestrel", realized_pnl: 48210, total_trades: 412, win_rate: 0.71 },
  { rank: 2, username: "edge_seeker", realized_pnl: 39680, total_trades: 388, win_rate: 0.66 },
  { rank: 3, username: "calibrated_ai", realized_pnl: 34115, total_trades: 502, win_rate: 0.63 },
  { rank: 4, username: "polly_maxi", realized_pnl: 26740, total_trades: 274, win_rate: 0.61 },
  { rank: 5, username: "delta_hunter", realized_pnl: 22190, total_trades: 341, win_rate: 0.59 },
  { rank: 6, username: "night_oracle", realized_pnl: 18420, total_trades: 208, win_rate: 0.64 },
  { rank: 7, username: "spread_smith", realized_pnl: 15330, total_trades: 297, win_rate: 0.57 },
  { rank: 8, username: "vega_vandal", realized_pnl: 12880, total_trades: 189, win_rate: 0.6 },
  { rank: 9, username: "brier_baron", realized_pnl: 9910, total_trades: 231, win_rate: 0.55 },
  { rank: 10, username: "kalshi_koda", realized_pnl: 7640, total_trades: 167, win_rate: 0.58 },
];

function formatWinRate(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function initials(name: string): string {
  return name.replace(/[^a-zA-Z0-9]/g, "").slice(0, 2).toUpperCase();
}

const PODIUM_STYLES = [
  { ring: "border-gold/50 bg-gold/10", medal: "🥇", glow: "shadow-[0_0_28px_rgba(246,194,68,0.25)]", order: "sm:order-2 sm:-translate-y-3" },
  { ring: "border-border-light bg-surface-2", medal: "🥈", glow: "shadow-lift", order: "sm:order-1" },
  { ring: "border-[#C6824A]/45 bg-[#C6824A]/10", medal: "🥉", glow: "shadow-lift", order: "sm:order-3" },
];

function Podium({ entries }: { entries: LeaderboardEntry[] }) {
  const top = entries.slice(0, 3);
  if (top.length < 3) return null;
  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-3 sm:items-end">
      {top.map((entry, i) => {
        const s = PODIUM_STYLES[i];
        return (
          <div
            key={entry.username}
            className={cn("rounded-2xl border p-4 text-center", s.ring, s.glow, s.order)}
          >
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-border-light bg-bg font-mono text-sm font-black text-text">
              {initials(entry.username)}
            </div>
            <div className="mt-2 text-lg">{s.medal}</div>
            <div className="mt-1 truncate text-sm font-black text-text">{entry.username}</div>
            <div className="mt-1 font-mono text-xl font-black tabular-nums text-primary">
              {formatUSD(entry.realized_pnl)}
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-muted">
              {formatWinRate(entry.win_rate)} win · {entry.total_trades} trades
            </div>
            <Link
              href="/mirror"
              className="mt-3 inline-flex w-full items-center justify-center rounded-lg border border-accent/40 bg-accent/12 px-3 py-1.5 text-xs font-black text-accent transition hover:bg-accent/20"
            >
              Copy trader
            </Link>
          </div>
        );
      })}
    </div>
  );
}

function ArenaSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="skeleton h-14 w-full rounded-xl" />
      ))}
    </div>
  );
}

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [demo, setDemo] = useState(false);
  const [sort, setSort] = useState<ArenaSort>("pnl");

  useEffect(() => {
    if (!API_BASE) {
      setEntries(DEMO_LEADERBOARD);
      setDemo(true);
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      try {
        const rows = await fetchLeaderboard();
        if (rows.length > 0) {
          setEntries(rows);
          setDemo(false);
        } else {
          setEntries(DEMO_LEADERBOARD);
          setDemo(true);
        }
      } catch {
        setEntries(DEMO_LEADERBOARD);
        setDemo(true);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const sorted = useMemo(() => {
    const copy = [...entries];
    if (sort === "active") copy.sort((a, b) => b.total_trades - a.total_trades);
    else if (sort === "winrate") copy.sort((a, b) => b.win_rate - a.win_rate);
    else copy.sort((a, b) => b.realized_pnl - a.realized_pnl);
    return copy.map((e, i) => ({ ...e, rank: i + 1 }));
  }, [entries, sort]);

  const summary = useMemo(() => {
    if (entries.length === 0) return null;
    const totalPnl = entries.reduce((sum, e) => sum + e.realized_pnl, 0);
    const totalTrades = entries.reduce((sum, e) => sum + e.total_trades, 0);
    const avgWin = entries.reduce((sum, e) => sum + e.win_rate, 0) / entries.length;
    return { totalPnl, totalTrades, avgWin, traders: entries.length };
  }, [entries]);

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Trader Arena"
        title="Leaderboard"
        subtitle="Top paper traders ranked across resolved markets. Copy any trader into the Mirror simulator — simulated funds only."
        actions={
          <Link
            href="/mirror"
            className="inline-flex items-center rounded-xl border border-border bg-surface px-4 py-2 text-sm font-black text-text transition hover:border-primary hover:text-primary"
          >
            Open Mirror
          </Link>
        }
      />

      {summary ? (
        <StatRow className="mb-6">
          <StatTile label="Arena P&L" value={formatUSD(summary.totalPnl)} deltaTone="up" delta="paper" accent />
          <StatTile label="Ranked traders" value={summary.traders.toLocaleString()} />
          <StatTile label="Total trades" value={summary.totalTrades.toLocaleString()} />
          <StatTile label="Avg win rate" value={formatWinRate(summary.avgWin)} />
        </StatRow>
      ) : null}

      {loading ? null : <Podium entries={sorted} />}

      <Panel
        padded={false}
        title="Standings"
        action={<SegTabs value={sort} onChange={setSort} options={SORT_OPTIONS} size="sm" />}
      >
        <div className="p-4 sm:p-5">
          {loading ? (
            <ArenaSkeleton />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs font-bold uppercase tracking-[0.08em] text-muted-2">
                    <th className="px-3 py-3">Rank</th>
                    <th className="px-3 py-3">Trader</th>
                    <th className="px-3 py-3 text-right">Realized P&amp;L</th>
                    <th className="px-3 py-3 text-right">Trades</th>
                    <th className="px-3 py-3 text-right">Win rate</th>
                    <th className="px-3 py-3 text-right">Copy</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((entry) => (
                    <tr
                      key={`${entry.username}`}
                      className="border-b border-border/60 transition last:border-0 hover:bg-surface-2/50"
                    >
                      <td className="px-3 py-3">
                        <span className="font-mono text-sm font-bold tabular-nums text-muted">
                          #{entry.rank}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span className="flex items-center gap-2.5">
                          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-border bg-surface-2 font-mono text-[11px] font-black text-text">
                            {initials(entry.username)}
                          </span>
                          <span className="truncate font-semibold text-text">{entry.username}</span>
                        </span>
                      </td>
                      <td
                        className={cn(
                          "px-3 py-3 text-right font-mono font-bold tabular-nums",
                          entry.realized_pnl >= 0 ? "text-primary" : "text-danger",
                        )}
                      >
                        {formatUSD(entry.realized_pnl)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums text-muted">
                        {entry.total_trades}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums text-text">
                        {formatWinRate(entry.win_rate)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <Link
                          href="/mirror"
                          className="inline-flex items-center rounded-lg border border-border px-2.5 py-1 text-xs font-black text-muted transition hover:border-accent hover:text-accent"
                        >
                          Copy
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Panel>

      {demo && !loading ? (
        <p className="mt-4 text-center text-xs text-muted-2">
          Showing demo standings. Connect the API to rank live paper traders.
        </p>
      ) : null}
    </PageShell>
  );
}
