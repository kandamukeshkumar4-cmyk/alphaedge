"use client";

// F01: public forecast reliability from GET /api/v1/track-record (G05).
// Reliability curve (predicted vs observed) + Brier-over-time + CLV histogram.
// Provisional caveat is prominent when thin_data; honest empty when no data.
import { useEffect, useState } from "react";
import {
  buildTrackRecordView,
  fetchPublicTrackRecord,
  type BrierPoint,
  type ClvBucketView,
  type ReliabilityPoint,
  type TrackRecordView,
} from "@/lib/track-record-api";
import { cn } from "@/lib/cn";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";

function ReliabilityCurve({ points }: { points: ReliabilityPoint[] }) {
  const size = 220;
  const pad = 24;
  const inner = size - pad * 2;
  const x = (v: number) => pad + v * inner;
  const y = (v: number) => pad + (1 - v) * inner;
  const maxCount = Math.max(1, ...points.map((p) => p.count));

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="h-auto w-full max-w-[280px]"
      role="img"
      aria-label="Reliability curve: predicted probability versus observed frequency"
    >
      {/* frame */}
      <rect
        x={pad}
        y={pad}
        width={inner}
        height={inner}
        className="fill-none stroke-border"
        strokeWidth={1}
      />
      {/* perfect-calibration diagonal */}
      <line
        x1={x(0)}
        y1={y(0)}
        x2={x(1)}
        y2={y(1)}
        className="stroke-muted-2"
        strokeWidth={1}
        strokeDasharray="4 4"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={x(p.predicted)}
          cy={y(p.observed)}
          r={3 + (p.count / maxCount) * 5}
          className="fill-primary/70 stroke-primary"
          strokeWidth={1}
        />
      ))}
      <text x={pad} y={size - 6} className="fill-muted-2 text-[9px]">
        predicted →
      </text>
    </svg>
  );
}

function BrierLine({ series }: { series: BrierPoint[] }) {
  const w = 320;
  const h = 140;
  const pad = 22;
  const values = series.map((s) => s.cumulative_brier);
  const maxV = Math.max(0.02, ...values);
  const minV = Math.min(0, ...values);
  const span = maxV - minV || 1;
  const px = (i: number) =>
    pad + (series.length <= 1 ? 0 : (i / (series.length - 1)) * (w - pad * 2));
  const py = (v: number) => pad + (1 - (v - minV) / span) * (h - pad * 2);
  const d = series.map((s, i) => `${i === 0 ? "M" : "L"}${px(i)},${py(s.cumulative_brier)}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-auto w-full"
      role="img"
      aria-label="Cumulative Brier score over time (lower is better)"
    >
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} className="stroke-border" strokeWidth={1} />
      <path d={d} className="fill-none stroke-accent" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {series.map((s, i) => (
        <circle key={i} cx={px(i)} cy={py(s.cumulative_brier)} r={2.5} className="fill-accent" />
      ))}
    </svg>
  );
}

function ClvHistogram({ buckets }: { buckets: ClvBucketView[] }) {
  const maxCount = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <div className="space-y-1.5">
      {buckets.map((b, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-16 shrink-0 text-right font-mono text-[10px] text-muted-2">{b.label}</span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-surface-2">
            <div
              className="h-full rounded bg-primary/60"
              style={{ width: `${(b.count / maxCount) * 100}%` }}
            />
          </div>
          <span className="w-6 shrink-0 font-mono text-[10px] text-muted">{b.count}</span>
        </div>
      ))}
    </div>
  );
}

function Card({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="mb-3">
        <h3 className="text-sm font-black tracking-tight text-text">{title}</h3>
        {hint ? <p className="mt-0.5 text-[11px] text-muted-2">{hint}</p> : null}
      </div>
      {children}
    </div>
  );
}

export function TrackRecordReliability() {
  const [view, setView] = useState<TrackRecordView | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    void fetchPublicTrackRecord(ctrl.signal).then((raw) => {
      setView(buildTrackRecordView(raw));
      setLoaded(true);
    });
    return () => ctrl.abort();
  }, []);

  if (!loaded) {
    return (
      <div className="grid gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-56 animate-pulse rounded-2xl border border-border bg-surface" />
        ))}
      </div>
    );
  }

  if (!view || !view.available) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center">
        <p className="text-base font-semibold text-text">No resolved forecasts yet</p>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
          The reliability curve, Brier trend, and CLV distribution populate from real market
          resolutions only — nothing is simulated or curated. Check back after markets settle.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="rounded-xl border border-border bg-surface-2/60 px-3.5 py-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Resolved</p>
          <p className="font-mono text-xl font-black text-text">
            n=<AnimatedNumber value={view.n} format={(v) => String(Math.round(v))} />
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface-2/60 px-3.5 py-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Brier</p>
          <p className="font-mono text-xl font-black text-text">{view.brierLabel}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface-2/60 px-3.5 py-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Mean CLV</p>
          <p
            className={cn(
              "font-mono text-xl font-black",
              view.clvMeanLabel.startsWith("+") ? "text-up" : view.clvMeanLabel.startsWith("-") ? "text-danger" : "text-text",
            )}
          >
            {view.clvMeanLabel}
          </p>
        </div>
        {view.lastUpdatedLabel ? (
          <span className="ml-auto text-[11px] text-muted-2">Updated {view.lastUpdatedLabel}</span>
        ) : null}
      </div>

      {view.caveat ? (
        <div className="flex items-start gap-2 rounded-xl border border-gold/40 bg-gold/10 px-4 py-3">
          <span className="mt-0.5 rounded-pill bg-gold/20 px-2 py-0.5 font-mono text-[10px] font-black uppercase text-gold">
            Provisional
          </span>
          <p className="text-sm font-semibold text-gold">{view.caveat}</p>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <MotionReveal delay={0}>
          <Card title="Reliability" hint="Predicted vs observed — dots on the diagonal are well-calibrated.">
            {view.hasReliability ? (
              <div className="flex justify-center">
                <ReliabilityCurve points={view.reliabilityPoints} />
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted">No filled calibration bins yet.</p>
            )}
          </Card>
        </MotionReveal>
        <MotionReveal delay={0.08}>
          <Card title="Brier over time" hint="Cumulative Brier per resolution — lower is better.">
            {view.hasBrierSeries ? (
              <BrierLine series={view.brierSeries} />
            ) : (
              <p className="py-8 text-center text-sm text-muted">
                No per-resolution timeline on this data source yet.
              </p>
            )}
          </Card>
        </MotionReveal>
        <MotionReveal delay={0.16}>
          <Card title="CLV distribution" hint={`Closing-line value across resolutions — ${view.clvPositiveShareLabel} positive.`}>
            {view.hasClv ? (
              <ClvHistogram buckets={view.clvBuckets} />
            ) : (
              <p className="py-8 text-center text-sm text-muted">No CLV samples yet.</p>
            )}
          </Card>
        </MotionReveal>
      </div>
    </div>
  );
}
