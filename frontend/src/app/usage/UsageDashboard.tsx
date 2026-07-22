"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import {
  getUsageSummary,
  USAGE_DEFAULT_DAYS,
  type ApiSource,
  type UsageDay,
  type UsageSummary,
} from "@/lib/usage-api";
import { useCountUp } from "@/lib/use-count-up";

import { UsageActivityChart } from "./UsageActivityChart";
import { formatUsageDate, USAGE_METRICS, type UsageMetric } from "./usage-metrics";

type UsageData = { summary: UsageSummary; source: ApiSource };

// ---------------------------------------------------------------------------
// Stat cards — 500ms count-up (UI-DIRECTION motion rules: the one permitted
// >400ms animation; useCountUp snaps instantly under reduced motion).
// ---------------------------------------------------------------------------

function StatCard({
  metric,
  total,
  dayCount,
  grandTotal,
  index,
}: {
  metric: UsageMetric;
  total: number;
  dayCount: number;
  grandTotal: number;
  index: number;
}) {
  const shown = useCountUp(total, 500);
  const perDay = dayCount > 0 ? (total / dayCount).toFixed(1) : "0.0";
  const share = grandTotal > 0 ? Math.round((total / grandTotal) * 100) : 0;

  return (
    <div
      data-testid="usage-stat-card"
      className={cn(
        "t-rise group relative overflow-hidden rounded-lg border border-border bg-surface/40 p-4",
        "transition duration-250 ease-swift hover:-translate-y-0.5 hover:border-border-light hover:bg-surface-2/60 hover:shadow-card",
        index === 1 && "t-stagger-1",
        index === 2 && "t-stagger-2",
        index === 3 && "t-stagger-3",
      )}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-0.5 opacity-70 transition-opacity duration-250 ease-swift group-hover:opacity-100"
        style={{ backgroundColor: metric.hex }}
      />
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className="h-2 w-2 rounded-[3px]"
          style={{ backgroundColor: metric.hex }}
        />
        <p className="font-mono text-[11px] font-semibold uppercase tracking-widest text-muted">
          {metric.label}
        </p>
      </div>
      <p
        data-testid={`usage-stat-${metric.key}-value`}
        className="mt-3 font-mono text-4xl font-semibold tabular-nums text-text"
      >
        {shown}
      </p>
      <p className="mt-1.5 font-mono text-[11px] tabular-nums text-muted-2">
        ≈ {perDay} / day · {share}% of activity
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loop V86 (X4) — "Paper research usage" card: a Runs-by-surface breakdown
// of the four activity metrics from the existing usage API, each with a
// per-day sparkline. Same no-red rule as the rest of the page — every series
// uses its metric token color (mint / blue / amber / gray).
// ---------------------------------------------------------------------------

function Sparkline({ values, hex }: { values: number[]; hex: string }) {
  const w = 132;
  const h = 30;
  const pad = 3;
  const max = Math.max(1, ...values);
  const n = values.length;
  const pts = values
    .map((v, i) => {
      const x = n <= 1 ? w / 2 : pad + (i / (n - 1)) * (w - 2 * pad);
      const y = h - pad - (v / max) * (h - 2 * pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      data-testid="usage-sparkline"
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={`per-day sparkline`}
      className="block w-full max-w-[140px]"
      preserveAspectRatio="none"
    >
      <polyline
        points={pts}
        fill="none"
        stroke={hex}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity={0.9}
      />
    </svg>
  );
}

function SurfaceCard({
  metric,
  total,
  dayCount,
  values,
  index,
}: {
  metric: UsageMetric;
  total: number;
  dayCount: number;
  values: number[];
  index: number;
}) {
  const shown = useCountUp(total, 500);
  const peak = values.length ? Math.max(...values) : 0;
  const perDay = dayCount > 0 ? (total / dayCount).toFixed(1) : "0.0";
  return (
    <div
      data-testid="usage-surface-card"
      className={cn(
        "t-rise group relative overflow-hidden rounded-lg border border-border bg-surface/40 p-4",
        "transition duration-250 ease-swift hover:-translate-y-0.5 hover:border-border-light hover:bg-surface-2/60 hover:shadow-card",
        index === 1 && "t-stagger-1",
        index === 2 && "t-stagger-2",
        index === 3 && "t-stagger-3",
      )}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-0.5 opacity-70"
        style={{ backgroundColor: metric.hex }}
      />
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="h-2 w-2 rounded-[3px]"
            style={{ backgroundColor: metric.hex }}
          />
          <p className="font-mono text-[11px] font-semibold uppercase tracking-widest text-muted">
            {metric.label}
          </p>
        </div>
        <p className="font-mono text-[10px] tabular-nums text-muted-2">
          peak {peak}/day
        </p>
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <p
          data-testid={`usage-surface-${metric.key}-value`}
          className="font-mono text-3xl font-semibold tabular-nums leading-none text-text"
        >
          {shown}
        </p>
        <Sparkline values={values} hex={metric.hex} />
      </div>
      <p className="mt-2 font-mono text-[11px] tabular-nums text-muted-2">
        ≈ {perDay} / day
      </p>
    </div>
  );
}

function UsageBySurface({
  days,
  totals,
}: {
  days: UsageDay[];
  totals: UsageSummary["totals"];
}) {
  return (
    <section
      aria-label="Runs by surface"
      className="t-rise t-stagger-3 rounded-lg border border-border bg-surface/40 p-4"
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-base font-bold tracking-tight text-text">
            Paper research usage
          </h2>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-widest text-muted">
            Runs by surface
          </p>
        </div>
        <p className="font-mono text-[11px] text-muted-2">
          {days.length}-day series · paper only
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="usage-by-surface">
        {USAGE_METRICS.map((m, i) => (
          <SurfaceCard
            key={m.key}
            metric={m}
            total={totals[m.key]}
            dayCount={days.length}
            values={days.map((d) => d[m.key])}
            index={i}
          />
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton — reserved heights everywhere (no CLS); the t-skeleton
// shimmer is killed by the global reduced-motion switch.
// ---------------------------------------------------------------------------

function UsageSkeleton() {
  return (
    <div data-testid="usage-skeleton" aria-hidden className="space-y-8">
      <div className="space-y-3">
        <div className="t-skeleton h-3 w-52" />
        <div className="t-skeleton h-9 w-full max-w-xl" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="t-skeleton h-[118px]" />
        ))}
      </div>
      <div className="t-skeleton h-[348px]" />
      <div className="t-skeleton h-[268px]" />
      <div className="t-skeleton h-[464px]" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export function UsageDashboard() {
  const [data, setData] = useState<UsageData | null>(null);

  useEffect(() => {
    let live = true;
    void getUsageSummary(USAGE_DEFAULT_DAYS).then((d) => {
      if (live) setData(d);
    });
    return () => {
      live = false;
    };
  }, []);

  if (!data) return <UsageSkeleton />;

  const { summary, source } = data;
  const { days, totals } = summary;
  const grandTotal =
    totals.sessions + totals.skill_runs + totals.scanner_runs + totals.briefs;
  const rows = [...days].reverse(); // newest calendar day reads first
  const grandRowTotal = (d: UsageDay) =>
    d.sessions + d.skill_runs + d.scanner_runs + d.briefs;

  return (
    <div data-testid="usage-dashboard" className="space-y-8">
      {/* Header */}
      <header className="t-rise">
        <p className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.22em] text-muted">
          <span aria-hidden className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-primary" />
          Paper desk · last {days.length} days
        </p>
        <div className="mt-2.5 flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
          <h1 className="text-3xl font-bold tracking-tight text-text sm:text-4xl">
            Usage{" "}
            <span className="text-lg font-medium text-muted sm:text-xl">
              — paper research activity
            </span>
          </h1>
          <div className="flex items-center gap-2">
            <span className="rounded border border-primary/30 bg-primary-dim/55 px-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-widest text-primary">
              Paper only
            </span>
            <span
              data-testid="usage-source"
              className="rounded border border-border bg-surface px-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-2"
            >
              {source}
            </span>
          </div>
        </div>
      </header>

      {/* Stat cards */}
      <section aria-label="14-day totals" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {USAGE_METRICS.map((m, i) => (
          <StatCard
            key={m.key}
            metric={m}
            total={totals[m.key]}
            dayCount={days.length}
            grandTotal={grandTotal}
            index={i}
          />
        ))}
      </section>

      {/* Stacked daily activity */}
      <section
        aria-label="Daily activity chart"
        className="t-rise t-stagger-2 rounded-lg border border-border bg-surface/40 p-4"
      >
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-muted">
            Daily activity — stacked
          </h2>
          <p className="font-mono text-[11px] tabular-nums text-muted-2">
            {days[0]?.date} → {days[days.length - 1]?.date}
          </p>
        </div>
        <UsageActivityChart days={days} totals={totals} />
      </section>

      {/* Runs by surface — per-metric sparklines (Loop V86 X4). */}
      <UsageBySurface days={days} totals={totals} />

      {/* 14-day log */}
      <section
        aria-label="Daily activity log"
        className="t-rise t-stagger-3 overflow-hidden rounded-lg border border-border bg-surface/40"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-4 py-3">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-muted">
            Daily log — last {days.length} days
          </h2>
          <p className="font-mono text-[11px] text-muted-2">Simulated research activity</p>
        </div>
        <div className="overflow-x-auto">
          <table data-testid="usage-table" className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border">
                <th
                  scope="col"
                  className="px-4 py-3 text-left font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-2"
                >
                  Date
                </th>
                {USAGE_METRICS.map((m) => (
                  <th
                    key={m.key}
                    scope="col"
                    className="px-4 py-3 text-right font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-2"
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="h-1.5 w-1.5 rounded-[2px]"
                        style={{ backgroundColor: m.hex }}
                      />
                      {m.column}
                    </span>
                  </th>
                ))}
                <th
                  scope="col"
                  className="px-4 py-3 text-right font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-2"
                >
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr
                  key={d.date}
                  data-testid="usage-table-row"
                  className="border-b border-border/60 transition-colors duration-250 ease-swift last:border-b-0 hover:bg-surface-2/50"
                >
                  <th scope="row" className="px-4 py-2.5 text-left font-medium text-text">
                    {formatUsageDate(d.date)}
                  </th>
                  {USAGE_METRICS.map((m) => (
                    <td
                      key={m.key}
                      className={cn(
                        "px-4 py-2.5 text-right font-mono tabular-nums",
                        d[m.key] === 0 ? "text-muted-2" : "text-text",
                      )}
                    >
                      {d[m.key]}
                    </td>
                  ))}
                  <td className="px-4 py-2.5 text-right font-mono font-semibold tabular-nums text-text">
                    {grandRowTotal(d)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-border bg-surface-2/40">
                <th
                  scope="row"
                  className="px-4 py-3 text-left font-mono text-[10px] font-semibold uppercase tracking-widest text-muted"
                >
                  {days.length}-day total
                </th>
                {USAGE_METRICS.map((m) => (
                  <td
                    key={m.key}
                    className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-text"
                  >
                    {totals[m.key]}
                  </td>
                ))}
                <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-primary">
                  {grandTotal}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  );
}
