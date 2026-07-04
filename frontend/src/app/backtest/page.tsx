"use client";

/**
 * U10 — /backtest page (under Research nav).
 *
 * UI contract (BUILD_LOOP_UNIFIED_UI.md §U10):
 *   - Pick agent/clone + date range → run replay
 *   - Equity curve (lightweight-charts)
 *   - Fill quality table (slippage vs mid)
 *   - Brier-over-time
 *   - "no-lookahead verified" badge
 *   - Honest empty/insufficient-data state (never fake a curve)
 *
 * PAPER_TRADING_ONLY: all results are paper simulations. Banner is permanent.
 */

import { useState } from "react";
import Link from "next/link";
import { BacktestRunner } from "@/components/BacktestRunner";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { FillQualityTable } from "@/components/FillQualityTable";
import { type BacktestRunResult, type BrierPoint } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function NoLookaheadBadge({ verified }: { verified: boolean }) {
  return (
    <span
      data-testid="no-lookahead-badge"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase",
        verified
          ? "bg-primary/10 text-primary"
          : "bg-danger/10 text-danger",
      )}
    >
      <span
        className={cn("h-1.5 w-1.5 rounded-full", verified ? "bg-primary" : "bg-danger")}
      />
      {verified ? "No-lookahead verified" : "Lookahead check failed"}
    </span>
  );
}

function BrierChart({ series }: { series: BrierPoint[] }) {
  if (series.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface px-4 py-6 text-center text-sm text-muted-2">
        No Brier series — insufficient trades
      </div>
    );
  }
  const last = series[series.length - 1];
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-sm font-semibold text-text">Brier score over time</span>
        <span className="font-mono text-xs text-muted-2">
          final = {last.brier.toFixed(4)} ({last.sample_count} samples)
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {series.map((pt, i) => (
          <div
            key={i}
            title={`${pt.timestamp.slice(0, 16)} | Brier ${pt.brier.toFixed(4)} | n=${pt.sample_count}`}
            className="group relative h-6 w-2 cursor-default rounded-sm"
            style={{
              backgroundColor: `hsl(${140 - pt.brier * 400}, 60%, 45%)`,
              opacity: 0.7 + 0.3 * (i / series.length),
            }}
          />
        ))}
      </div>
      <p className="mt-2 text-[10px] text-muted-2">
        Hover a bar for timestamp + score. Green = lower (better) Brier.
      </p>
    </div>
  );
}

function ResultPanel({ result }: { result: BacktestRunResult }) {
  const pnl = (result.final_equity ?? result.initial_equity) - result.initial_equity;
  const isPositive = pnl >= 0;

  return (
    <div className="mt-6 space-y-4">
      {/* Summary row */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded-pill bg-surface-2 px-3 py-1 font-mono text-xs text-muted">
          {result.market_slug}
        </span>
        <NoLookaheadBadge verified={result.no_lookahead_verified} />
        <span className="rounded-pill bg-surface-2 px-3 py-1 font-mono text-xs text-muted">
          {result.snapshot_count} snapshots
        </span>
        <span className="rounded-pill bg-surface-2 px-3 py-1 font-mono text-xs text-muted">
          {result.trade_count} trades
        </span>
        {result.brier_final !== null && (
          <span className="rounded-pill bg-surface-2 px-3 py-1 font-mono text-xs text-muted">
            Brier {result.brier_final.toFixed(4)}
          </span>
        )}
        <span className="ml-auto text-xs text-muted-2">{timeAgo(result.created_at)}</span>
      </div>

      {/* Insufficient data honest state */}
      {result.insufficient_data && (
        <div className="rounded-xl border border-border bg-surface p-6 text-center">
          <p className="text-base font-semibold text-text">Insufficient data</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
            Fewer than 2 odds snapshots exist in this date range for{" "}
            <span className="font-mono">{result.market_slug}</span>. The equity
            curve and fill stats are not fabricated.
          </p>
        </div>
      )}

      {/* Equity curve */}
      {!result.insufficient_data && (
        <div className="rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-sm font-semibold text-text">Equity curve</span>
            <span
              className={cn(
                "font-mono text-sm font-semibold",
                isPositive ? "text-primary" : "text-danger",
              )}
            >
              {isPositive ? "+" : ""}${Math.abs(pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </div>
          <EquityCurveChart
            equityCurve={result.equity_curve}
            initialEquity={result.initial_equity}
          />
        </div>
      )}

      {/* Fill quality */}
      {!result.insufficient_data && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-text">Fill quality</h3>
          <FillQualityTable fillQuality={result.fill_quality} />
        </div>
      )}

      {/* Brier over time */}
      {!result.insufficient_data && <BrierChart series={result.brier_over_time} />}

      {/* Params */}
      <details className="rounded-xl border border-border bg-surface">
        <summary className="cursor-pointer px-4 py-3 text-xs font-semibold text-muted hover:text-text">
          Replay parameters
        </summary>
        <div className="border-t border-border px-4 py-3 font-mono text-[11px] text-muted-2">
          <p>ID: {result.id}</p>
          <p>
            Range: {result.start_date.slice(0, 10)} → {result.end_date.slice(0, 10)}
          </p>
          <p>Initial equity: ${result.initial_equity.toLocaleString()}</p>
          <p>paper_trading_only: {String(result.paper_trading_only)}</p>
          <p>no_lookahead_verified: {String(result.no_lookahead_verified)}</p>
        </div>
      </details>
    </div>
  );
}

export default function BacktestPage() {
  const [result, setResult] = useState<BacktestRunResult | null>(null);

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Backtest</h1>
        <span className="rounded-pill bg-accent-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent">
          RESEARCH
        </span>
        <span className="rounded-pill border border-border px-2.5 py-0.5 font-mono text-[11px] font-semibold text-muted">
          PAPER TRADING ONLY
        </span>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-muted">
        Replay an agent over historical odds snapshots with a realistic fill model — fills
        are worse than mid-price by a documented spread and slippage function. Results are
        never fabricated: if there are fewer than 2 snapshots in the selected range, you will
        see an honest empty state.{" "}
        <Link href="/research" className="font-semibold text-accent hover:underline">
          ← Research
        </Link>
      </p>

      {/* Runner form */}
      <BacktestRunner onResult={setResult} />

      {/* Result panel or placeholder */}
      {result ? (
        <ResultPanel result={result} />
      ) : (
        <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface/50 px-6 py-12 text-center">
          <p className="text-base font-semibold text-text">No replay run yet</p>
          <p className="mx-auto mt-1.5 max-w-sm text-sm text-muted">
            Fill in the form above and click <strong>Run replay</strong>. Results will appear
            here — the equity curve, fill quality, and Brier score are computed from real
            historical odds snapshots.
          </p>
        </div>
      )}

      {/* Paper-trading disclaimer (permanent) */}
      <p className="mt-8 text-center text-xs text-muted-2">
        All backtest results are paper simulations using simulated funds. No real money is
        involved. Replays use a fill model that applies spread and slippage — fills are
        always worse than mid-price.
      </p>
    </main>
  );
}
