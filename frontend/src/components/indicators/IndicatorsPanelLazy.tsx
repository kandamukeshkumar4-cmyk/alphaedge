"use client";

// Loop 99 AU3 — lazy boundary for the TA panel's lightweight-charts chart.
// Mirrors PriceChartLazy: splits lightweight-charts out of the market-detail
// first-load JS and reserves the panel's height (header ~40 + tiles ~76 +
// chart 240 + legend/footer ~60 ≈ 430) so the dynamic swap causes no CLS.

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import type { IndicatorsPanel as IndicatorsPanelComponent } from "./IndicatorsPanel";

type IndicatorsPanelProps = ComponentProps<typeof IndicatorsPanelComponent>;

const IndicatorsPanelInner = dynamic(
  () => import("./IndicatorsPanel").then((m) => ({ default: m.IndicatorsPanel })),
  { ssr: false, loading: () => null },
);

export function IndicatorsPanel(props: IndicatorsPanelProps) {
  return (
    <div style={{ minHeight: 430 }}>
      <IndicatorsPanelInner {...props} />
    </div>
  );
}
