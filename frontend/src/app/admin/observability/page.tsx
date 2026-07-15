"use client";

// U12 + Loop V38 Observability admin page.
// Ops boards (loops, sources, jobs, stats) plus traces / drift / SLOs.
// All data sourced from real backend endpoints — no fabricated numbers.

import { AdminStatsCard } from "@/components/admin/AdminStatsCard";
import { DriftChart } from "@/components/admin/DriftChart";
import { LoopHealthBoard } from "@/components/admin/LoopHealthBoard";
import { SourceHealthBoard } from "@/components/admin/SourceHealthBoard";
import { SloTiles } from "@/components/admin/SloTiles";
import { SystemHealthCard } from "@/components/admin/SystemHealthCard";
import { TraceExplorer } from "@/components/admin/TraceExplorer";
import { useAdminApiKey } from "@/lib/admin-context";

export default function ObservabilityPage() {
  const apiKey = useAdminApiKey();

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
          Loop heartbeats, connector sources, job runs, system stats, traces,
          calibration drift, and latency SLOs. Live backend data only.
        </p>
      </header>

      <LoopHealthBoard />
      <SourceHealthBoard />
      <AdminStatsCard apiKey={apiKey} />
      <SystemHealthCard apiKey={apiKey} limit={20} />
      <SloTiles />
      <DriftChart />
      <TraceExplorer />
    </>
  );
}
