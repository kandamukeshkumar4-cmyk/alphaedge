"use client";

// D02: walk-forward transparency from GET /api/v1/backtest/summary (H02).
// Cumulative Brier + flat-stake ROI lines (inline SVG, TrackRecordReliability
// style), model-vs-market Brier tiles, thin_data "Provisional" caveat, honest
// empty at n=0. Real resolutions only — never a fabricated curve.
import { useEffect, useState } from "react";
import {
  buildBacktestSummaryView,
  fetchBacktestSummary,
  type BacktestSummaryView,
  type SeriesPoint,
} from "@/lib/backtest-summary-api";
import { cn } from "@/lib/cn";

function WalkForwardLine({
  series,
  label,
  stroke,
  fill,
  formatValue,
}: {
  series: SeriesPoint[];
  label: string;
  stroke: string;
  fill: string;
  formatValue: (v: number) => string;
}) {
  const w = 320;
  const h = 140;
  const pad = 22;
  const values = series.map((s) => s.value);
  const maxV = Math.max(0.02, ...values);
  const minV = Math.min(0, ...values);
  const span = maxV - minV || 1;
  const px = (i: number) =>
    pad + (series.length <= 1 ? 0 : (i / (series.length - 1)) * (w - pad * 2));
  const py = (v: number) => pad + (1 - (v - minV) / span) * (h - pad * 2);
  const d = series.map((s, i) => `${i === 0 ? "M" : "L"}${px(i)},${py(s.value)}`).join(" ");
  const last = series[series.length - 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-auto w-full" role="img" aria-label={label}>
      <title>{label}</title>
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} className="stroke-border" strokeWidth={1} />
      <path d={d} className={cn("fill-none", stroke)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {series.map((s, i) => (
        <circle key={s.seq} cx={px(i)} cy={py(s.value)} r={2.5} className={fill}>
          <title>{`resolution ${s.seq}: ${formatValue(s.value)}`}</title>
        </circle>
      ))}
      <text x={w - pad} y={py(last.value) - 6} textAnchor="end" className="fill-muted-2 text-[9px] font-mono">
        {formatValue(last.value)}
      </text>
    </svg>
  );
}

function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/60 px-3.5 py-2">
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">{label}</p>
      <p className={cn("font-mono text-xl font-black", tone ?? "text-text")}>{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-muted-2">{hint}</p> : null}
    </div>
  );
}

function ChartCard({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="mb-3">
        <h3 className="text-sm font-black tracking-tight text-text">{title}</h3>
        <p className="mt-0.5 text-[11px] text-muted-2">{hint}</p>
      </div>
      {children}
    </div>
  );
}

export function BacktestWalkForward() {
  const [view, setView] = useState<BacktestSummaryView | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void fetchBacktestSummary(ctrl.signal).then((raw) => {
      setView(buildBacktestSummaryView(raw));
    });
    return () => ctrl.abort();
  }, []);

  if (!view) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="h-48 animate-pulse rounded-2xl border border-border bg-surface" />
        ))}
      </div>
    );
  }

  if (!view.available) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center">
        <p className="text-base font-semibold text-text">
          {view.reachable ? "No resolved forecasts yet" : "Walk-forward summary unreachable"}
        </p>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
          {view.reachable
            ? "Walk-forward Brier and ROI populate from real market resolutions only — nothing is simulated or curated. Check back after markets settle."
            : "The live API did not answer — start the backend or set NEXT_PUBLIC_API_URL to see the walk-forward record."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {view.caveat ? (
        <div className="flex items-start gap-2 rounded-xl border border-gold/40 bg-gold/10 px-4 py-3">
          <span className="mt-0.5 rounded-pill bg-gold/20 px-2 py-0.5 font-mono text-[10px] font-black uppercase text-gold">
            Provisional
          </span>
          <p className="text-sm font-semibold text-gold">{view.caveat}</p>
        </div>
      ) : null}

      {/* Model-vs-market tiles */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Resolved" value={`n=${view.nLabel}`} hint={view.lastUpdatedLabel ? `updated ${view.lastUpdatedLabel}` : undefined} />
        <Tile label="Model Brier" value={view.brierLabel} hint={view.brierVerdict ?? undefined} />
        <Tile label="Market Brier" value={view.marketBrierLabel} hint="implied-price baseline" />
        <Tile
          label="Flat-stake ROI"
          value={view.roiLabel}
          hint={`${view.betsLabel} bets · ${view.pnlLabel} paper P&L`}
          tone={view.roiTone === "up" ? "text-up" : view.roiTone === "down" ? "text-danger" : "text-text"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Walk-forward Brier" hint="Cumulative Brier per real resolution — lower is better.">
          {view.hasBrierSeries ? (
            <WalkForwardLine
              series={view.brierSeries}
              label="Walk-forward cumulative Brier score per resolution (lower is better)"
              stroke="stroke-accent"
              fill="fill-accent"
              formatValue={(v) => v.toFixed(3)}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted">
              Fewer than 2 resolutions — no line to draw yet.
            </p>
          )}
        </ChartCard>
        <ChartCard title="Walk-forward ROI" hint="Cumulative flat-stake (1-contract) paper ROI — starts at the first bet.">
          {view.hasRoiSeries ? (
            <WalkForwardLine
              series={view.roiSeries}
              label="Walk-forward cumulative flat-stake paper ROI per resolution"
              stroke="stroke-primary"
              fill="fill-primary"
              formatValue={(v) => `${(v * 100).toFixed(0)}%`}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted">
              Fewer than 2 bets so far — the ROI line starts at the first bet.
            </p>
          )}
        </ChartCard>
      </div>

      <p className="text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
    </div>
  );
}
