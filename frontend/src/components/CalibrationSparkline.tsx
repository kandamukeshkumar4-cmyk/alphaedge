"use client";

/**
 * CalibrationSparkline — mini reliability diagram for U03 DecisionCard.
 *
 * P07: now fetches REAL calibration bins from GET /api/v1/calibration
 * (eval_routes.py) instead of the previous synthetic x-spread. Each plotted
 * point is a real bucket: mean predicted probability (X) vs observed outcome
 * frequency (Y), sized by real sample count. When the total resolved sample
 * is thin, the curve is labelled "provisional" and never over-claims.
 */

import { useEffect, useState } from "react";
import {
  buildCalibrationCurve,
  fetchCalibrationBins,
  type CalibrationCurve,
} from "@/lib/calibration-api";

type Props = {
  className?: string;
};

const W = 120;
const H = 72;
const PAD = 8;

function toSvgX(p: number) {
  return PAD + p * (W - 2 * PAD);
}

function toSvgY(p: number) {
  // Y axis: 0=bottom, 1=top in calibration; SVG is top-down
  return H - PAD - p * (H - 2 * PAD);
}

const EMPTY_CURVE: CalibrationCurve = { points: [], totalN: 0, provisional: true };

export function CalibrationSparkline({ className }: Props) {
  const [curve, setCurve] = useState<CalibrationCurve>(EMPTY_CURVE);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    fetchCalibrationBins(controller.signal)
      .then((bins) => {
        if (cancelled) return;
        setCurve(buildCalibrationCurve(bins));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  if (loading) {
    return (
      <div className={className}>
        <div className="h-[72px] w-full animate-pulse rounded bg-surface-2" />
      </div>
    );
  }

  const { points, totalN, provisional } = curve;

  if (points.length === 0) {
    return (
      <div className={className}>
        <p className="text-[11px] text-muted">
          Calibration curve — no resolved data yet
        </p>
      </div>
    );
  }

  // Build SVG path through the real calibration points.
  const pathD = points
    .map(
      (pt, i) =>
        `${i === 0 ? "M" : "L"} ${toSvgX(pt.predicted).toFixed(1)} ${toSvgY(pt.observed).toFixed(1)}`,
    )
    .join(" ");

  return (
    <div className={className}>
      <div className="flex items-center justify-between text-[11px] text-muted">
        <span className="font-semibold uppercase tracking-wide">Calibration</span>
        <span className="font-mono">
          {provisional ? (
            <span className="text-gold">Provisional · n={totalN}</span>
          ) : (
            <span>
              n=<span className="text-text">{totalN}</span> resolved
            </span>
          )}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="mt-1 w-full"
        role="img"
        aria-label={`Calibration reliability curve from ${totalN} resolved outcomes${provisional ? " (provisional — thin data)" : ""}`}
      >
        {/* Perfect-calibration diagonal */}
        <line
          x1={toSvgX(0)}
          y1={toSvgY(0)}
          x2={toSvgX(1)}
          y2={toSvgY(1)}
          stroke="var(--color-muted-2, #555)"
          strokeWidth="1"
          strokeDasharray="3 2"
          opacity="0.5"
        />
        {/* Observed calibration line */}
        {points.length > 1 && (
          <path
            d={pathD}
            fill="none"
            stroke="var(--color-accent, #00C9A0)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        )}
        {/* Data points */}
        {points.map((pt, i) => (
          <circle
            key={i}
            cx={toSvgX(pt.predicted)}
            cy={toSvgY(pt.observed)}
            r="2.5"
            fill="var(--color-accent, #00C9A0)"
          />
        ))}
      </svg>
      <div className="mt-0.5 flex justify-between text-[10px] text-muted-2">
        <span>Predicted</span>
        <span>Observed</span>
      </div>
    </div>
  );
}
