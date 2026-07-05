"use client";

/**
 * U10 — BacktestRunner form.
 * Lets the user pick a market slug, date range, and fill params,
 * then triggers a replay run via POST /api/v1/backtest/run.
 *
 * Honest empty state: never fabricates a result.
 * PAPER_TRADING_ONLY: all results carry paper_trading_only=true.
 */

import { useState } from "react";
import { cn } from "@/lib/cn";
import {
  triggerBacktestRun,
  type BacktestRunResult,
  type BacktestRunRequest,
} from "@/lib/alphaedge-api";

interface BacktestRunnerProps {
  onResult: (result: BacktestRunResult) => void;
}

const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

// Date helpers computed once at module load (outside React render) to avoid
// the react-hooks/purity lint rule about calling impure functions during render.
function _isoDate(offset = 0): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offset);
  return d.toISOString().slice(0, 10);
}
const _TODAY = _isoDate(0);
const _SEVEN_DAYS_AGO = _isoDate(-7);

export function BacktestRunner({ onResult }: BacktestRunnerProps) {
  const [slug, setSlug] = useState(CANONICAL_SLUG);
  const [startDate, setStartDate] = useState(_SEVEN_DAYS_AGO);
  const [endDate, setEndDate] = useState(_TODAY);
  const [spread, setSpread] = useState("0.02");
  const [edgeThreshold, setEdgeThreshold] = useState("0.05");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setError(null);
    setLoading(true);
    try {
      const req: BacktestRunRequest = {
        market_slug: slug.trim(),
        start_date: new Date(startDate + "T00:00:00Z").toISOString(),
        end_date: new Date(endDate + "T23:59:59Z").toISOString(),
        spread: parseFloat(spread),
        edge_threshold: parseFloat(edgeThreshold),
        initial_equity: 10_000,
        stake: 100,
      };
      const result = await triggerBacktestRun(req);
      if (!result) {
        setError("Replay failed — check that the backend is running and the market slug exists.");
      } else {
        onResult(result);
      }
    } catch {
      setError("Unexpected error. Check the backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="text-base font-semibold text-text">Backtest Replay</h2>
        <span className="rounded-pill bg-accent-dim px-2 py-0.5 font-mono text-[10px] font-bold text-accent">
          PAPER ONLY
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {/* Market slug */}
        <div className="sm:col-span-2 lg:col-span-3">
          <label className="mb-1 block text-xs font-medium text-muted">
            Market slug
          </label>
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder={CANONICAL_SLUG}
            className="w-full rounded-lg border border-border bg-bg px-3 py-1.5 font-mono text-sm text-text placeholder:text-muted-2 focus:border-accent focus:outline-none"
          />
        </div>

        {/* Date range */}
        <div>
          <label className="mb-1 block text-xs font-medium text-muted">Start date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full rounded-lg border border-border bg-bg px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted">End date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full rounded-lg border border-border bg-bg px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
          />
        </div>

        {/* Spread */}
        <div>
          <label className="mb-1 block text-xs font-medium text-muted">
            Spread{" "}
            <span className="text-muted-2">(bid-ask, e.g. 0.02)</span>
          </label>
          <input
            type="number"
            min="0"
            max="0.5"
            step="0.005"
            value={spread}
            onChange={(e) => setSpread(e.target.value)}
            className="w-full rounded-lg border border-border bg-bg px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
          />
        </div>

        {/* Edge threshold */}
        <div>
          <label className="mb-1 block text-xs font-medium text-muted">
            Edge threshold{" "}
            <span className="text-muted-2">(min model edge, e.g. 0.05)</span>
          </label>
          <input
            type="number"
            min="0"
            max="0.5"
            step="0.01"
            value={edgeThreshold}
            onChange={(e) => setEdgeThreshold(e.target.value)}
            className="w-full rounded-lg border border-border bg-bg px-3 py-1.5 text-sm text-text focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={handleRun}
          disabled={loading || !slug.trim()}
          className={cn(
            "rounded-pill px-5 py-2 text-sm font-semibold transition",
            loading || !slug.trim()
              ? "cursor-not-allowed bg-surface-2 text-muted-2"
              : "bg-accent text-bg hover:bg-accent/80",
          )}
        >
          {loading ? "Running replay…" : "Run replay"}
        </button>
        <span className="text-xs text-muted-2">
          Simulated fills — no real funds
        </span>
      </div>
    </div>
  );
}
