"use client";

// U12 — Calibration drift chart.
// Shows rolling Brier vs the baseline, with the alarm threshold line.
// All numbers sourced from the real /api/v1/admin/observability/drift endpoint.
// Honest unavailable state: when data is absent, says so — no fabricated values.

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchDrift, type DriftResponse } from "@/lib/observability-api";

export function DriftChart() {
  const [data, setData] = useState<DriftResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const result = await fetchDrift();
    setData(result);
    setLoading(false);
  };

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text">Calibration Drift</h2>
          <p className="text-xs text-muted">
            Rolling Brier vs baseline — alarm fires when drift exceeds threshold.
          </p>
        </div>
        {data?.alarm && (
          <span className="rounded border border-danger/50 bg-danger-dim px-2 py-1 text-xs font-bold text-danger">
            ALARM
          </span>
        )}
        <button
          className="ml-2 rounded border border-border-light px-3 py-1 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:opacity-50"
          disabled={loading}
          onClick={() => void load()}
          type="button"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {loading ? (
        <p className="p-4 text-sm text-muted">Loading drift data…</p>
      ) : !data ? (
        <p className="p-4 text-sm text-muted">
          Drift data unavailable — backend not reachable.
        </p>
      ) : (
        <div className="p-4 space-y-4">
          {/* KPI tiles */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiTile
              label="Rolling Brier"
              value={data.rolling_brier != null ? data.rolling_brier.toFixed(4) : "—"}
              note={data.insufficient_data ? "insufficient data" : `n=${data.n_claims}`}
              highlight={false}
            />
            <KpiTile
              label="Baseline Brier"
              value={data.baseline_brier.toFixed(4)}
              note="reference"
              highlight={false}
            />
            <KpiTile
              label="Drift"
              value={data.drift != null ? (data.drift > 0 ? "+" : "") + data.drift.toFixed(4) : "—"}
              note={data.drift != null && data.drift > 0 ? "degraded" : data.drift != null ? "improved" : "no data"}
              highlight={data.alarm}
            />
            <KpiTile
              label="Threshold"
              value={`±${data.threshold.toFixed(2)}`}
              note="alarm trigger"
              highlight={false}
            />
          </div>

          {/* Drift bar chart (history points) */}
          {data.history.length > 0 ? (
            <div>
              <p className="mb-2 text-xs font-semibold text-muted-2 uppercase tracking-wide">
                Brier by window (overall dimension)
              </p>
              <div className="flex items-end gap-3">
                {data.history.map((pt) => (
                  <BriefBar
                    key={pt.window_days}
                    windowDays={pt.window_days}
                    brier={pt.brier}
                    baseline={data.baseline_brier}
                    threshold={data.threshold}
                  />
                ))}
                {/* Baseline reference */}
                <div className="flex flex-col items-center gap-1">
                  <div
                    className="w-10 rounded-t bg-muted-2/50"
                    style={{ height: `${Math.round(data.baseline_brier * 200)}px` }}
                  />
                  <p className="text-[10px] text-muted-2">baseline</p>
                </div>
              </div>
              <p className="mt-2 text-[10px] text-muted">
                Lower is better. Threshold line at baseline ± {data.threshold.toFixed(2)}.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted">
              No historical aggregate data yet — drift chart appears once claims are graded.
            </p>
          )}

          {data.insufficient_data && (
            <p className="rounded border border-gold/30 bg-gold/10 px-3 py-2 text-xs text-gold">
              Insufficient data: fewer than the configured window of graded claims are available.
              Drift alarm cannot fire until the window is full.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function KpiTile({
  label,
  value,
  note,
  highlight,
}: {
  label: string;
  value: string;
  note: string;
  highlight: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        highlight
          ? "border-danger/50 bg-danger-dim"
          : "border-border bg-surface-2",
      )}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-2">{label}</p>
      <p
        className={cn(
          "mt-1 text-lg font-bold tabular-nums",
          highlight ? "text-danger" : "text-text",
        )}
      >
        {value}
      </p>
      <p className="text-[10px] text-muted">{note}</p>
    </div>
  );
}

function BriefBar({
  windowDays,
  brier,
  baseline,
  threshold,
}: {
  windowDays: number;
  brier: number;
  baseline: number;
  threshold: number;
}) {
  const height = Math.max(4, Math.round(brier * 200));
  const isDrifted = Math.abs(brier - baseline) > threshold;
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={cn(
          "w-10 rounded-t",
          isDrifted ? "bg-danger/70" : "bg-primary/70",
        )}
        style={{ height: `${height}px` }}
        title={`Brier: ${brier.toFixed(4)}`}
      />
      <p className="text-[10px] text-muted">{windowDays === 0 ? "all" : `${windowDays}d`}</p>
    </div>
  );
}
