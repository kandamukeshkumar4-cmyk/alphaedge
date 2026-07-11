"use client";

// T01 (Loop V12) — lazy boundary for the lightweight-charts probability-history
// chart on the market detail route. Same rationale as PriceChartLazy: the chart
// is client-only (createChart in useEffect, data fetched async) and already
// renders its own pulse skeleton while loading, so deferring the lightweight-
// charts chunk to mount time is behaviourally identical. A reserved min-height
// keeps the layout stable through the swap.

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import type { ProbabilityHistoryChart as ProbabilityHistoryChartComponent } from "./ProbabilityHistoryChart";

type ChartProps = ComponentProps<typeof ProbabilityHistoryChartComponent>;

const Inner = dynamic(
  () =>
    import("./ProbabilityHistoryChart").then((m) => ({
      default: m.ProbabilityHistoryChart,
    })),
  { ssr: false, loading: () => null },
);

export function ProbabilityHistoryChart(props: ChartProps) {
  const reserve = (props.height ?? 100) + 32;
  return (
    <div style={{ minHeight: reserve }}>
      <Inner {...props} />
    </div>
  );
}
