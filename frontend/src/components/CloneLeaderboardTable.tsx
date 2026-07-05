"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import type {
  CloneLeaderboardEntry,
  CloneScorecardResponse,
} from "@/lib/leaderboard-api";
import { fetchCloneScorecard } from "@/lib/leaderboard-api";
import { CloneProfile } from "@/components/CloneProfile";

// ── Micro helpers ──────────────────────────────────────────────────────────────

function fmt2(v: number | null): string {
  if (v === null) return "—";
  return v.toFixed(3);
}

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return `${Math.round(v * 100)}%`;
}

function fmtPnl(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}`;
}

function ProvisionalBadge() {
  return (
    <span
      title="Fewer than 30 graded claims — calibration score is provisional"
      className="ml-1 inline-flex items-center rounded border border-amber-400/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-300"
    >
      provisional
    </span>
  );
}

// ── Mini sparkline (PnL trajectory from claim history) ────────────────────────

function PnlSparkline({ entries }: { entries: CloneLeaderboardEntry[] }) {
  // Build a tiny SVG line from cumulative PnL across graded claims
  // Since we only have total paper_pnl at this level, draw a simple bar indicator
  const max = Math.max(...entries.map((e) => Math.abs(e.paper_pnl)), 1);
  return (
    <span className="flex items-center gap-0.5" aria-hidden>
      {entries.slice(0, 5).map((e) => {
        const h = Math.round((Math.abs(e.paper_pnl) / max) * 16) + 2;
        return (
          <span
            key={e.clone_id}
            className={cn(
              "w-1 rounded-sm",
              e.paper_pnl >= 0 ? "bg-primary/60" : "bg-red-400/60",
            )}
            style={{ height: `${h}px` }}
          />
        );
      })}
    </span>
  );
}

// ── Sort button ────────────────────────────────────────────────────────────────

function SortButton({
  active,
  dir,
  children,
  onClick,
}: {
  active: boolean;
  dir: "asc" | "desc";
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 transition",
        active ? "text-accent font-bold" : "text-muted hover:text-text",
      )}
    >
      {children}
      {active && <span className="text-[10px]">{dir === "asc" ? "↑" : "↓"}</span>}
    </button>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  entries: CloneLeaderboardEntry[];
  loading: boolean;
  error: string | null;
  sortBy: "brier" | "pnl";
  onSortChange: (s: "brier" | "pnl") => void;
}

export function CloneLeaderboardTable({
  entries,
  loading,
  error,
  sortBy,
  onSortChange,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scorecard, setScorecard] = useState<CloneScorecardResponse | null>(null);
  const [scorecardLoading, setScorecardLoading] = useState(false);

  async function handleRowClick(cloneId: string) {
    if (selectedId === cloneId) {
      setSelectedId(null);
      setScorecard(null);
      return;
    }
    setSelectedId(cloneId);
    setScorecardLoading(true);
    try {
      const card = await fetchCloneScorecard(cloneId);
      setScorecard(card);
    } catch {
      setScorecard(null);
    } finally {
      setScorecardLoading(false);
    }
  }

  if (error) {
    return (
      <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
        {error}
      </p>
    );
  }

  if (loading) {
    return (
      <div className="space-y-3" aria-hidden>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton h-12 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (!loading && entries.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-lg font-bold text-text">No clones yet</p>
        <p className="mt-2 text-sm text-muted">
          Build a clone in the{" "}
          <a href="/clones" className="text-accent hover:underline">
            Clones
          </a>{" "}
          section to appear on the leaderboard.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-[0.08em] text-muted">
              <th className="px-3 py-3">Rank</th>
              <th className="px-3 py-3">Clone</th>
              <th className="px-3 py-3 text-right">
                <SortButton
                  active={sortBy === "brier"}
                  dir="asc"
                  onClick={() => onSortChange("brier")}
                >
                  Brier
                </SortButton>
              </th>
              <th className="px-3 py-3 text-right">Accuracy</th>
              <th className="px-3 py-3 text-right">Claims</th>
              <th className="px-3 py-3 text-right">
                <SortButton
                  active={sortBy === "pnl"}
                  dir="desc"
                  onClick={() => onSortChange("pnl")}
                >
                  Paper PnL
                </SortButton>
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, idx) => {
              const isSelected = selectedId === entry.clone_id;
              return (
                <>
                  <tr
                    key={entry.clone_id}
                    onClick={() => void handleRowClick(entry.clone_id)}
                    className={cn(
                      "cursor-pointer border-b border-border/70 transition last:border-0",
                      isSelected
                        ? "bg-accent/5"
                        : "hover:bg-surface-2",
                    )}
                  >
                    <td className="px-3 py-3">
                      <span className="font-mono text-sm font-bold text-muted tabular-nums">
                        #{idx + 1}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-col gap-0.5">
                        <span className="font-semibold text-text">
                          {entry.name}
                          {entry.provisional && <ProvisionalBadge />}
                        </span>
                        <span className="text-[11px] text-muted">
                          v{entry.version} &middot; {entry.nodes.join(", ")}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums text-text">
                      {fmt2(entry.brier)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums text-muted">
                      {fmtPct(entry.accuracy)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums text-muted">
                      {entry.n_graded}
                    </td>
                    <td
                      className={cn(
                        "px-3 py-3 text-right font-mono font-bold tabular-nums",
                        entry.paper_pnl >= 0 ? "text-primary" : "text-red-400",
                      )}
                    >
                      {fmtPnl(entry.paper_pnl)}
                    </td>
                  </tr>
                  {isSelected && (
                    <tr key={`${entry.clone_id}-detail`} className="bg-surface-2/50">
                      <td colSpan={6} className="px-3 py-4">
                        {scorecardLoading ? (
                          <div className="skeleton h-32 w-full rounded-xl" aria-hidden />
                        ) : scorecard ? (
                          <CloneProfile scorecard={scorecard} />
                        ) : (
                          <p className="text-sm text-muted">
                            Profile unavailable — no backend connection.
                          </p>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
