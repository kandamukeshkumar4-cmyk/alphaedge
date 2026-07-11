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
  { ssr: false, loading: () => null },
);

export function PriceChart(props: PriceChartProps) {
  // Reserve header (~60px) + chart height so the lazy swap causes no CLS.
  const reserve = (props.height ?? 360) + 60;
  return (
    <div style={{ minHeight: reserve }}>
      <PriceChartInner {...props} />
    </div>
  );
}
