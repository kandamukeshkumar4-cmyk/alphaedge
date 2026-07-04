"use client";

import { cn } from "@/lib/cn";
import type { CloneScorecardResponse, CloneRunGrade } from "@/lib/leaderboard-api";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmt3(v: number | null): string {
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

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function VerdictBadge({ verdict }: { verdict: string }) {
  if (verdict === "correct") {
    return (
      <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
        correct
      </span>
    );
  }
  if (verdict === "incorrect") {
    return (
      <span className="inline-flex items-center rounded-full border border-red-400/30 bg-red-400/10 px-2 py-0.5 text-[11px] font-bold text-red-400">
        incorrect
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] font-medium text-muted">
      void
    </span>
  );
}

function MetricTile({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <p className="text-[10px] font-bold uppercase tracking-wide text-muted">{label}</p>
      <p
        className={cn(
          "mt-1 font-mono text-lg font-bold tabular-nums",
          highlight ? "text-accent" : "text-text",
        )}
      >
        {value}
      </p>
      {sub && <p className="text-[11px] text-muted-2">{sub}</p>}
    </div>
  );
}

// ── Claim history table ───────────────────────────────────────────────────────

function ClaimHistoryTable({ grades }: { grades: CloneRunGrade[] }) {
  if (grades.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted">
        No graded claims yet — runs are scored after the horizon elapses.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-xs">
        <thead>
          <tr className="border-b border-border text-[10px] uppercase tracking-wide text-muted">
            <th className="px-2 py-2">Market</th>
            <th className="px-2 py-2">Direction</th>
            <th className="px-2 py-2 text-right">Price at run</th>
            <th className="px-2 py-2 text-right">Price at horizon</th>
            <th className="px-2 py-2 text-center">Verdict</th>
            <th className="px-2 py-2 text-right">Confidence</th>
            <th className="px-2 py-2 text-right">Date</th>
          </tr>
        </thead>
        <tbody>
          {grades.map((g) => (
            <tr key={g.run_id} className="border-b border-border/50 last:border-0">
              <td className="px-2 py-2 font-mono text-[11px] text-muted">
                {g.market_slug}
              </td>
              <td className="px-2 py-2 font-medium text-text capitalize">
                {g.direction}
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-muted">
                {(g.price_at_run * 100).toFixed(1)}¢
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-muted">
                {g.price_at_horizon !== null
                  ? `${(g.price_at_horizon * 100).toFixed(1)}¢`
                  : "—"}
              </td>
              <td className="px-2 py-2 text-center">
                <VerdictBadge verdict={g.verdict} />
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-muted">
                {fmtPct(g.confidence)}
              </td>
              <td className="px-2 py-2 text-right text-muted-2">
                {fmtDate(g.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────

interface Props {
  scorecard: CloneScorecardResponse;
}

export function CloneProfile({ scorecard }: Props) {
  const { config, metrics } = scorecard;

  return (
    <div className="space-y-4">
      {/* Config section */}
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-surface p-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-muted">
            Nodes
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {config.nodes.map((n) => (
              <span
                key={n}
                className="rounded border border-border bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-text"
              >
                {n}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-surface p-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-muted">
            Markets watched
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {config.markets.length === 0 ? (
              <span className="text-xs text-muted">All markets</span>
            ) : (
              config.markets.map((m) => (
                <span
                  key={m}
                  className="rounded border border-border bg-surface-2 px-2 py-0.5 font-mono text-[10px] text-muted"
                >
                  {m}
                </span>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricTile
          label="Brier score"
          value={fmt3(metrics.brier)}
          sub={metrics.provisional ? "provisional" : "calibrated"}
          highlight={metrics.brier !== null && metrics.brier < 0.25}
        />
        <MetricTile
          label="Accuracy"
          value={fmtPct(metrics.accuracy)}
          sub={`${metrics.n_graded} graded`}
        />
        <MetricTile
          label="Paper PnL"
          value={fmtPnl(metrics.paper_pnl)}
          sub="confidence-weighted"
        />
        <MetricTile
          label="Version"
          value={`v${config.version}`}
          sub={`edge ≥ ${(config.edge_threshold * 100).toFixed(0)}%`}
        />
      </div>

      {metrics.provisional && (
        <p className="rounded-lg border border-amber-400/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-300">
          Provisional — this clone needs {30 - metrics.n_graded} more graded
          claims before its calibration score is reliable.
        </p>
      )}

      {/* Claim history */}
      <div>
        <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-muted">
          Claim history
        </p>
        <ClaimHistoryTable grades={scorecard.claim_history} />
      </div>

      {/* Disclaimer */}
      <p className="text-[10px] text-muted-2">{scorecard.disclaimer}</p>
    </div>
  );
}
