"use client";

/**
 * V92 PU3 — Paper calibration reliability plot from analytics.calibration.buckets.
 * Predicted-prob bucket × actual rate — simple bar/scatter. Mint/blue only.
 * Empty buckets → honest "insufficient data" (never fabricate).
 */

import { cn } from "@/lib/cn";
import type { PortfolioCalibrationBucket } from "@/lib/portfolio-analytics-api";

const BLOCK_MIN_H = 220;

function bucketMidpoint(label: string): number | null {
  const m = /^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$/.exec(label.trim());
  if (!m) return null;
  const lo = Number(m[1]);
  const hi = Number(m[2]);
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
  return (lo + hi) / 2;
}

export function AnalyticsCalibrationChart({
  buckets,
}: {
  buckets: PortfolioCalibrationBucket[];
}) {
  if (buckets.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-2xl border border-border bg-surface px-4 py-10 text-center"
        style={{ minHeight: BLOCK_MIN_H }}
        data-testid="analytics-calibration-empty"
      >
        <p className="text-sm font-semibold text-text">Insufficient data</p>
        <p className="mt-1 text-[11px] text-muted">
          Paper calibration appears once settled trades fill probability buckets.
        </p>
      </div>
    );
  }

  const maxN = Math.max(1, ...buckets.map((b) => b.n));
  const size = 240;
  const pad = 28;
  const inner = size - pad * 2;
  const x = (v: number) => pad + v * inner;
  const y = (v: number) => pad + (1 - v) * inner;

  return (
    <div
      className="rounded-2xl border border-border bg-surface p-4 sm:p-5"
      style={{ minHeight: BLOCK_MIN_H }}
      data-testid="analytics-calibration"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-black tracking-tight text-text">
          Paper calibration
        </h3>
        <span className="rounded-pill border border-border px-2 py-0.5 font-mono text-[10px] font-semibold text-muted-2">
          RELIABILITY
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,240px)_1fr]">
        <svg
          viewBox={`0 0 ${size} ${size}`}
          className="h-auto w-full max-w-[240px]"
          role="img"
          aria-label="Paper calibration: predicted probability bucket versus actual win rate"
        >
          <title>Paper calibration reliability</title>
          <rect
            x={pad}
            y={pad}
            width={inner}
            height={inner}
            className="fill-none stroke-border"
            strokeWidth={1}
          />
          <line
            x1={x(0)}
            y1={y(0)}
            x2={x(1)}
            y2={y(1)}
            className="stroke-muted-2"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          {buckets.map((b, i) => {
            const mid = bucketMidpoint(b.predicted_prob_bucket);
            if (mid === null) return null;
            const r = 3 + (b.n / maxN) * 6;
            return (
              <circle
                key={`${b.predicted_prob_bucket}-${i}`}
                cx={x(Math.min(1, Math.max(0, mid)))}
                cy={y(Math.min(1, Math.max(0, b.actual_rate)))}
                r={r}
                className="fill-primary/70 stroke-primary"
                strokeWidth={1}
              />
            );
          })}
          <text x={pad} y={size - 8} className="fill-muted-2 text-[9px]">
            predicted →
          </text>
          <text
            x={10}
            y={pad + 8}
            className="fill-muted-2 text-[9px]"
            transform={`rotate(-90 10 ${pad + 8})`}
          >
            actual
          </text>
        </svg>

        <div className="space-y-1.5" data-testid="analytics-calibration-bars">
          {buckets.map((b) => (
            <div
              key={b.predicted_prob_bucket}
              className="flex items-center gap-2"
            >
              <span className="w-16 shrink-0 text-right font-mono text-[10px] text-muted-2">
                {b.predicted_prob_bucket}
              </span>
              <div
                className="h-3 flex-1 overflow-hidden rounded bg-surface-2"
                aria-hidden
              >
                <div
                  className={cn(
                    "h-full rounded",
                    b.actual_rate >= (bucketMidpoint(b.predicted_prob_bucket) ?? 0.5)
                      ? "bg-primary/70"
                      : "bg-secondary/70",
                  )}
                  style={{
                    width: `${Math.min(100, Math.max(4, b.actual_rate * 100))}%`,
                  }}
                />
              </div>
              <span className="w-14 shrink-0 font-mono text-[10px] text-muted">
                {(b.actual_rate * 100).toFixed(0)}% · n={b.n}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
