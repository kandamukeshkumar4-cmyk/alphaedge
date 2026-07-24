"use client";

// T01 (Loop V12) — lazy boundary for the lightweight-charts price chart.
// lightweight-charts (~large 3rd-party) was pulled into the first-load JS of
// every route that renders a chart (/trade, /markets/[slug], /markets/view).
// Loading it through next/dynamic (ssr:false) splits it into its own chunk that
// only downloads when the chart actually mounts — no first-paint content change:
// the chart is client-only today anyway (createChart runs in useEffect and its
// candle data streams in async), so callers see the same behaviour. A skeleton
// sized to the requested height reserves the space to avoid any layout shift.

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import type { PriceChart as PriceChartComponent } from "./PriceChart";

type PriceChartProps = ComponentProps<typeof PriceChartComponent>;

const PriceChartInner = dynamic(
  () => import("./PriceChart").then((m) => ({ default: m.PriceChart })),
  {
    ssr: false,
    // loop104 a11y: while the lazy chunk loads, expose the chart region as a
    // named image (role=img + aria-label) instead of nothing. This both gives
    // AT users an announced placeholder and makes the BUG-V28-02 regression
    // deterministic (the named region exists before the chunk resolves, so a
    // slow chunk load can no longer time out the 30s wait). Absolute-inset so
    // it fills the reserved box at any height without adding layout shift.
    loading: () => (
      <div
        role="img"
        aria-label="Price history chart"
        aria-busy="true"
        className="skeleton absolute inset-0 rounded-xl"
      />
    ),
  },
);

export function PriceChart(props: PriceChartProps) {
  // Reserve header (~60px) + chart height so the lazy swap causes no CLS.
  const reserve = (props.height ?? 360) + 60;
  return (
    <div className="relative" style={{ minHeight: reserve }}>
      <PriceChartInner {...props} />
    </div>
  );
}
