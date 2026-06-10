"use client";

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard-api";
import { formatUSD } from "@/lib/mock-data";

function formatWinRate(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-500/15 px-2.5 py-1 text-xs font-black text-amber-300">
        🏆 #1
      </span>
    );
  }
  if (rank === 2) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-300/30 bg-slate-400/15 px-2.5 py-1 text-xs font-black text-slate-200">
        🥈 #2
      </span>
    );
  }
  if (rank === 3) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-orange-400/35 bg-orange-500/15 px-2.5 py-1 text-xs font-black text-orange-300">
        🥉 #3
      </span>
    );
  }
  return <span className="font-mono text-sm font-bold text-muted tabular-nums">#{rank}</span>;
}

function LeaderboardSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="skeleton h-14 w-full rounded-xl" />
      ))}
    </div>
  );
}

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!API_BASE) {
      setError("Set NEXT_PUBLIC_API_URL to load the leaderboard.");
      setLoading(false);
      return;
    }

    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const rows = await fetchLeaderboard();
        setEntries(rows);
      } catch (err) {
        setEntries([]);
        setError(err instanceof Error ? err.message : "Failed to load leaderboard.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <main className="mx-auto max-w-[960px] px-4 py-8 sm:px-5">
      <div className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">Loop N</p>
        <h1 className="mt-1 text-3xl font-black tracking-tight text-text">Leaderboard</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Top paper traders ranked by realized P&amp;L across resolved markets.
        </p>
      </div>

      <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
        {error ? (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        ) : null}

        {loading ? <LeaderboardSkeleton /> : null}

        {!loading && !error && entries.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-lg font-bold text-text">Be the first to trade</p>
            <p className="mt-2 text-sm text-muted">
              Place paper trades on open markets to climb the leaderboard.
            </p>
          </div>
        ) : null}

        {!loading && entries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs font-bold uppercase tracking-[0.08em] text-muted">
                  <th className="px-3 py-3">Rank</th>
                  <th className="px-3 py-3">Trader</th>
                  <th className="px-3 py-3 text-right">Realized P&amp;L</th>
                  <th className="px-3 py-3 text-right">Trades</th>
                  <th className="px-3 py-3 text-right">Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={`${entry.rank}-${entry.username}`}
                    className="border-b border-border/70 last:border-0"
                  >
                    <td className="px-3 py-3">
                      <RankBadge rank={entry.rank} />
                    </td>
                    <td className="px-3 py-3 font-semibold text-text">{entry.username}</td>
                    <td
                      className={cn(
                        "px-3 py-3 text-right font-mono font-bold tabular-nums",
                        entry.realized_pnl >= 0 ? "text-primary" : "text-red-400",
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </main>
  );
}
