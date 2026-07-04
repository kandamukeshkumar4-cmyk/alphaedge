"use client";

// U12 Observability admin page.
// Panels: agent-run trace explorer, calibration drift chart, latency SLO tiles.
// All data sourced from real backend endpoints — no fabricated numbers.

import { TraceExplorer } from "@/components/admin/TraceExplorer";
import { DriftChart } from "@/components/admin/DriftChart";
import { SloTiles } from "@/components/admin/SloTiles";

export default function ObservabilityPage() {
  return (
    <>
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
          Observability
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-text">
          System Observability
        </h1>
        <p className="mt-2 text-sm text-muted">
          Agent-run trace explorer, calibration drift, and latency SLO panels.
          All metrics sourced live from the backend — no fabricated values.
        </p>
      </header>

      <SloTiles />
      <DriftChart />
      <TraceExplorer />
    </>
  );
}
