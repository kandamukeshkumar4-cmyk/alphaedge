"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchDriftSeries, type DriftPoint, type DriftSeriesResponse } from "@/lib/eval-api";

export function DriftSeriesPanel() {
  const [data, setData] = useState<DriftSeriesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setData(await fetchDriftSeries());
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const latest = data?.series[0] ?? null;
  const chartPoints = useMemo(
    () => [...(data?.series ?? [])].reverse().filter((point) => point.rolling_brier !== null),
    [data],
  );

  return (
    <section className="mt-10 rounded-2xl border border-border bg-surface" data-testid="drift-series-panel">
      <header className="flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-start sm:justify-between">
        <section>
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-primary">ForecastScore</p>
          <h2 className="mt-1 text-lg font-black text-text">Calibration drift history</h2>
          <p className="mt-1 text-sm text-muted">
            Persisted rolling Brier and calibration error snapshots. Lower error is better.
          </p>
        </section>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="min-h-10 rounded-lg border border-border-light px-3 text-xs font-bold text-muted transition hover:border-primary hover:text-primary disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </header>

      {loading ? (
        <p className="px-4 py-6 text-sm text-muted">Loading drift snapshots…</p>
      ) : !data ? (
        <p className="px-4 py-6 text-sm text-muted">Drift data is unavailable right now.</p>
      ) : data.series.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">
          No drift snapshots yet. This panel will populate after the evaluation worker records a window.
        </p>
      ) : (
        <section className="space-y-5 p-4">
          {data.latest_degraded ? (
            <p className="rounded-lg border border-danger/40 bg-danger-dim px-3 py-2 text-sm font-bold text-danger" role="status">
              Latest snapshot is degraded. Review the underlying evaluation window before treating this model as healthy.
            </p>
          ) : (
            <p className="rounded-lg border border-primary/30 bg-primary-dim px-3 py-2 text-sm font-semibold text-primary" role="status">
              Latest snapshot is within the recorded drift guardrail.
            </p>
          )}

          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricTile label="Latest Brier" value={formatMetric(latest?.rolling_brier)} />
            <MetricTile label="Latest ECE" value={formatMetric(latest?.rolling_ece)} />
            <MetricTile label="Window size" value={latest ? latest.window_n.toLocaleString() : "—"} />
            <MetricTile label="Snapshots" value={data.count.toLocaleString()} />
          </dl>

          {chartPoints.length > 1 ? <DriftChart points={chartPoints} /> : (
            <p className="rounded-lg border border-border bg-surface-2 px-3 py-3 text-sm text-muted">
              One usable Brier snapshot is available. A history chart appears after at least two snapshots.
            </p>
          )}

          <section className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-xs">
              <caption className="sr-only">Recent calibration drift snapshots</caption>
              <thead className="border-b border-border text-[10px] uppercase tracking-[0.08em] text-muted-2">
                <tr>
                  <th className="px-2 py-2 font-bold">Computed</th>
                  <th className="px-2 py-2 font-bold">N</th>
                  <th className="px-2 py-2 font-bold">Rolling Brier</th>
                  <th className="px-2 py-2 font-bold">Rolling ECE</th>
                  <th className="px-2 py-2 font-bold">Delta</th>
                  <th className="px-2 py-2 font-bold">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.series.slice(0, 10).map((point) => (
                  <DriftRow key={point.id} point={point} />
                ))}
              </tbody>
            </table>
          </section>

          <p className="text-xs text-muted-2">
            Paper-trading evaluation only. These values describe recorded forecasts; they are not a live execution signal.
          </p>
        </section>
      )}
    </section>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-border bg-surface-2 px-3 py-3">
      <dt className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">{label}</dt>
      <dd className="mt-1 font-mono text-lg font-black tabular-nums text-text">{value}</dd>
    </article>
  );
}

function DriftChart({ points }: { points: DriftPoint[] }) {
  const values = points.flatMap((point) => point.rolling_brier === null ? [] : [point.rolling_brier]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 0.01;
  const width = 640;
  const height = 180;
  const padding = 24;
  const coordinates = points.map((point, index) => ({
    point,
    x: padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2),
    y: point.rolling_brier === null
      ? height - padding
      : height - padding - ((point.rolling_brier - min) / range) * (height - padding * 2),
  }));

  return (
    <section aria-label="Rolling Brier chart" className="rounded-xl border border-border bg-bg p-3">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.08em] text-muted-2">Rolling Brier</p>
      <svg className="h-44 w-full overflow-visible text-accent" role="img" viewBox={`0 0 ${width} ${height}`}>
        <title>Rolling Brier over recorded evaluation windows</title>
        <line x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} stroke="currentColor" strokeOpacity="0.2" />
        <polyline
          fill="none"
          points={coordinates.map(({ x, y }) => `${x},${y}`).join(" ")}
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
        {coordinates.map(({ point, x, y }) => (
          <circle key={point.id} cx={x} cy={y} fill="currentColor" r="4">
            <title>{`${formatMetric(point.rolling_brier)} at ${formatDate(point.computed_at)}`}</title>
          </circle>
        ))}
      </svg>
      <p className="mt-1 text-[10px] text-muted-2">
        Range {min.toFixed(4)}–{max.toFixed(4)} · newest point is on the right
      </p>
    </section>
  );
}

function DriftRow({ point }: { point: DriftPoint }) {
  return (
    <tr>
      <td className="px-2 py-2 text-muted">{formatDate(point.computed_at)}</td>
      <td className="px-2 py-2 font-mono tabular-nums text-muted">{point.window_n.toLocaleString()}</td>
      <td className="px-2 py-2 font-mono tabular-nums text-text">{formatMetric(point.rolling_brier)}</td>
      <td className="px-2 py-2 font-mono tabular-nums text-muted">{formatMetric(point.rolling_ece)}</td>
      <td className="px-2 py-2 font-mono tabular-nums text-muted">{formatMetric(point.brier_delta)}</td>
      <td className="px-2 py-2">
        <span className={point.degraded ? "rounded border border-danger/40 bg-danger-dim px-2 py-1 font-bold text-danger" : "rounded border border-primary/30 bg-primary-dim px-2 py-1 font-bold text-primary"}>
          {point.degraded ? "Degraded" : "Within guardrail"}
        </span>
      </td>
    </tr>
  );
}

function formatMetric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Unknown time";
}
