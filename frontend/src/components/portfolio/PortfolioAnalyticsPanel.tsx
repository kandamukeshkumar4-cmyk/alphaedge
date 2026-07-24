"use client";

/**
 * V92 PU2 — Portfolio Analytics section (paper P&L / win rate / equity curve).
 * Live-first via portfolio-analytics-api; mint/blue/amber only (no danger-red).
 * Count-up 500ms; skeletons reserve height; prefers-reduced-motion via CountUp.
 */

import { useEffect, useState } from "react";

import { CountUp } from "@/components/CountUp";
import { AnalyticsEquityChart } from "@/components/portfolio/AnalyticsEquityChart";
import { cn } from "@/lib/cn";
import {
  ANALYTICS_DAY_OPTIONS,
  fetchPortfolioAnalytics,
  isEmptyPortfolioAnalytics,
  type AnalyticsDays,
  type PortfolioAnalytics,
} from "@/lib/portfolio-analytics-api";

const STAT_CARD_MIN_H = 96;
const EQUITY_BLOCK_MIN_H = 280;

type Tone = "neutral" | "up" | "down";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "text-text",
  up: "text-primary",
  down: "text-secondary", // blue — never danger-red (UI-DIRECTION)
};

function moneyTone(value: number): Tone {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

function formatSignedMoney(n: number): string {
  const abs = Math.abs(n).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (n > 0) return `+$${abs}`;
  if (n < 0) return `−$${abs}`;
  return `$${abs}`;
}

function StatCard({
  label,
  value,
  format,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: number;
  format: (n: number) => string;
  tone?: Tone;
  hint?: string;
}) {
  return (
    <div
      className="rounded-2xl border border-border bg-surface p-4"
      style={{ minHeight: STAT_CARD_MIN_H }}
      data-testid="analytics-stat-card"
    >
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted">
        {label}
      </p>
      <p className={cn("mt-2 font-mono text-2xl font-black", TONE_CLASS[tone])}>
        <CountUp value={value} durationMs={500} format={format} />
      </p>
      {hint ? (
        <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div data-testid="analytics-skeleton" className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div
            key={i}
            className="skeleton rounded-2xl"
            style={{ minHeight: STAT_CARD_MIN_H }}
          />
        ))}
      </div>
      <div
        className="skeleton rounded-2xl"
        style={{ minHeight: EQUITY_BLOCK_MIN_H }}
      />
    </div>
  );
}

export function PortfolioAnalyticsPanel({ token }: { token: string | null }) {
  const [days, setDays] = useState<AnalyticsDays>(30);
  const [data, setData] = useState<PortfolioAnalytics | null>(null);
  const [source, setSource] = useState<"live" | "mock" | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let dead = false;
    const ctrl = new AbortController();
    setLoading(true);
    void fetchPortfolioAnalytics({
      days,
      token,
      signal: ctrl.signal,
    }).then((result) => {
      if (dead) return;
      setData(result.data);
      setSource(result.source);
      setLoading(false);
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [days, token]);

  return (
    <section
      aria-label="Portfolio analytics"
      className="space-y-4"
      data-testid="portfolio-analytics"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-black tracking-tight text-text">
            Analytics
          </h2>
          <p className="mt-0.5 text-[11px] text-muted-2">
            Paper performance only — simulated funds, no execution.
            {source === "mock" ? " · Offline mock" : null}
          </p>
        </div>
        <div
          className="inline-flex rounded-xl border border-border bg-surface-2/40 p-0.5"
          role="group"
          aria-label="Analytics window"
          data-testid="analytics-days-selector"
        >
          {ANALYTICS_DAY_OPTIONS.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => setDays(opt)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-bold transition",
                days === opt
                  ? "bg-accent text-bg"
                  : "text-muted hover:text-text",
              )}
              aria-pressed={days === opt}
            >
              {opt}d
            </button>
          ))}
        </div>
      </div>

      {loading || !data ? (
        <AnalyticsSkeleton />
      ) : isEmptyPortfolioAnalytics(data) ? (
        <div
          className="rounded-2xl border border-border bg-surface px-4 py-10 text-center"
          style={{ minHeight: EQUITY_BLOCK_MIN_H }}
          data-testid="analytics-empty"
        >
          <p className="text-lg font-semibold text-text">
            No paper trades in this window
          </p>
          <p className="mt-2 text-sm text-muted">
            Place and settle paper bets to see realized P&amp;L, win rate, and
            the equity curve.
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Realized P&L"
              value={data.summary.total_realized}
              format={formatSignedMoney}
              tone={moneyTone(data.summary.total_realized)}
              hint="paper"
            />
            <StatCard
              label="Unrealized P&L"
              value={data.summary.total_unrealized}
              format={formatSignedMoney}
              tone={moneyTone(data.summary.total_unrealized)}
              hint="paper"
            />
            <StatCard
              label="Win rate"
              value={data.summary.win_rate * 100}
              format={(n) => `${n.toFixed(0)}%`}
              tone="neutral"
              hint={`${data.summary.trades_closed} closed`}
            />
            <StatCard
              label="Trades"
              value={data.summary.trades_closed + data.summary.trades_open}
              format={(n) => String(Math.round(n))}
              tone="neutral"
              hint={`${data.summary.trades_open} open · paper`}
            />
          </div>

          <div
            className="rounded-2xl border border-border bg-surface p-4 sm:p-5"
            style={{ minHeight: EQUITY_BLOCK_MIN_H }}
          >
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-black tracking-tight text-text">
                Equity curve
              </h3>
              <span className="rounded-pill border border-border px-2 py-0.5 font-mono text-[10px] font-semibold text-muted-2">
                PAPER
              </span>
            </div>
            <AnalyticsEquityChart series={data.pnl_series} />
          </div>
        </>
      )}
    </section>
  );
}
