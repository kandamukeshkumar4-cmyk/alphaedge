"use client";

// U12 — Agent-run trace explorer admin panel.
// Shows recent agent runs with per-node timings and I/O snapshots.
// Read-only, no order submission.

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchTraces, type AgentRun } from "@/lib/observability-api";

export function TraceExplorer() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setLoading(true);
      const data = await fetchTraces(20);
      if (alive) {
        setRuns(data.runs);
        setLoading(false);
      }
    };
    void load();
    return () => {
      alive = false;
    };
  }, []);

  const selectedRun = runs.find((r) => r.run_id === selectedRunId) ?? null;

  return (
    <section className="rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text">Agent-Run Trace Explorer</h2>
          <p className="text-xs text-muted">
            Recent agent graph runs — per-node timings and I/O snapshots.
          </p>
        </div>
        <button
          className="rounded border border-border-light px-3 py-1 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:opacity-50"
          disabled={loading}
          onClick={() => {
            setLoading(true);
            void fetchTraces(20).then((d) => {
              setRuns(d.runs);
              setLoading(false);
            });
          }}
          type="button"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {loading ? (
        <p className="p-4 text-sm text-muted">Loading runs…</p>
      ) : runs.length === 0 ? (
        <p className="p-4 text-sm text-muted">
          No agent runs recorded yet. Runs are recorded when the agent graph executes for a market.
        </p>
      ) : (
        <div className="flex flex-col lg:flex-row">
          {/* Run list */}
          <div className="w-full shrink-0 overflow-y-auto border-b border-border lg:w-72 lg:border-b-0 lg:border-r">
            {runs.map((run) => (
              <button
                key={run.run_id}
                className={cn(
                  "w-full px-4 py-3 text-left transition hover:bg-surface-2",
                  selectedRunId === run.run_id && "bg-primary-dim",
                )}
                onClick={() =>
                  setSelectedRunId(run.run_id === selectedRunId ? null : run.run_id)
                }
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs text-text">{run.market_slug}</span>
                  <RunStatusBadge status={run.status} />
                </div>
                <div className="mt-0.5 flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-muted-2">{run.graph_version}</span>
                  <span className="text-[10px] text-muted">{formatDate(run.created_at)}</span>
                </div>
              </button>
            ))}
          </div>

          {/* Step detail */}
          <div className="min-w-0 flex-1 p-4">
            {selectedRun ? (
              <RunDetail run={selectedRun} />
            ) : (
              <p className="text-sm text-muted">Select a run to inspect its steps.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function RunDetail({ run }: { run: AgentRun }) {
  const [openStep, setOpenStep] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <p className="text-sm font-semibold text-text">{run.market_slug}</p>
        <RunStatusBadge status={run.status} />
        <span className="ml-auto text-xs text-muted">{run.steps.length} steps</span>
      </div>

      {run.steps.length === 0 ? (
        <p className="text-sm text-muted">No steps recorded for this run.</p>
      ) : (
        <ol className="space-y-2">
          {run.steps.map((step, idx) => (
            <li key={`${step.step_name}-${idx}`} className="rounded-lg border border-border bg-bg">
              <button
                className="flex w-full items-center justify-between px-3 py-2 text-left"
                onClick={() => setOpenStep(openStep === step.step_name ? null : step.step_name)}
                type="button"
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary-dim text-[10px] font-bold text-primary">
                    {idx + 1}
                  </span>
                  <span className="font-mono text-xs font-semibold text-text">
                    {step.step_name}
                  </span>
                </div>
                <span className="text-[10px] text-muted">{formatDate(step.created_at)}</span>
              </button>

              {openStep === step.step_name && (
                <div className="border-t border-border px-3 py-2">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-2">
                        Input
                      </p>
                      <pre className="max-h-48 overflow-auto rounded bg-surface-2 p-2 font-mono text-[10px] text-muted">
                        {JSON.stringify(step.input_data, null, 2)}
                      </pre>
                    </div>
                    <div>
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-2">
                        Output
                      </p>
                      <pre className="max-h-48 overflow-auto rounded bg-surface-2 p-2 font-mono text-[10px] text-muted">
                        {JSON.stringify(step.output_data, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function RunStatusBadge({ status }: { status: string }) {
  const classes =
    status === "approved"
      ? "border-up/40 bg-up/10 text-up"
      : "border-danger/40 bg-danger-dim text-danger";
  return (
    <span className={cn("inline-flex rounded border px-2 py-0.5 text-[10px] font-semibold", classes)}>
      {status}
    </span>
  );
}

function formatDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "medium" });
}
