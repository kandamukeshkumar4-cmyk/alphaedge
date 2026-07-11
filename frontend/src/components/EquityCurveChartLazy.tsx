"use client";

// T01 (Loop V12) — lazy boundary for the lightweight-charts equity-curve chart
// on the /backtest route. The chart only renders after a backtest run resolves
// (conditional, below the controls) and is client-only, so deferring the
// lightweight-charts chunk to mount time is behaviourally identical. Reserved
// min-height keeps the layout stable through the swap.

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import type { EquityCurveChart as EquityCurveChartComponent } from "./EquityCurveChart";

type ChartProps = ComponentProps<typeof EquityCurveChartComponent>;

const Inner = dynamic(
  () =>
    import("./EquityCurveChart").then((m) => ({
      default: m.EquityCurveChart,
    })),
  { ssr: false, loading: () => null },
);

export function EquityCurveChart(props: ChartProps) {
  const reserve = props.height ?? 260;
  return (
    <div style={{ minHeight: reserve }}>
      <Inner {...props} />
    </div>
  );
}
