"use client";

// U12 + Loop V38 Observability admin page.
// Ops boards (loops) plus agent-run traces, calibration drift, latency SLOs.
// All data sourced from real backend endpoints — no fabricated numbers.

import { TraceExplorer } from "@/components/admin/TraceExplorer";
import { DriftChart } from "@/components/admin/DriftChart";
import { LoopHealthBoard } from "@/components/admin/LoopHealthBoard";
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
          Loop heartbeats, agent-run traces, calibration drift, and latency SLOs.
          All metrics sourced live from the backend — no fabricated values.
        </p>
      </header>

      <LoopHealthBoard />
      <SloTiles />
      <DriftChart />
      <TraceExplorer />
    </>
  );
}
