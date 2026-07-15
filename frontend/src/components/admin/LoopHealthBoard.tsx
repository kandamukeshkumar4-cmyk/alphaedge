"use client";

// O1 — Loop health board on /admin/observability.
// Public GET /api/v1/system/loops; 30s auto-refresh; honest empty/error;
// heartbeat age warns when age > 2× interval.

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  fetchLoops,
  formatAgeSec,
  heartbeatAgeSec,
  isHeartbeatStale,
  type LoopHeartbeat,
} from "@/lib/observability-api";

const REFRESH_MS = 30_000;

export function LoopHealthBoard() {
  const [loops, setLoops] = useState<LoopHeartbeat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchLoops();
    setNowMs(Date.now());
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setLoops([]);
      return;
    }
    setError(null);
    setLoops(result.data.loops);
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  return (
    <section className="rounded-xl border border-border bg-surface" id="loop-health">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text">Loop health</h2>
          <p className="text-xs text-muted">
            Background loop heartbeats — refreshes every 30s. Age warns past 2× interval.
          </p>
        </div>
        <button
          className="rounded border border-border-light px-3 py-1 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:opacity-50"
          disabled={loading}
          onClick={() => void load()}
          type="button"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error ? (
        <p role="alert" className="p-4 text-sm text-danger">
          {error}
        </p>
      ) : loading && loops.length === 0 ? (
        <p className="p-4 text-sm text-muted">Loading loop heartbeats…</p>
      ) : loops.length === 0 ? (
        <p className="p-4 text-sm text-muted">No loops reported.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
          {loops.map((loop) => (
            <LoopCard key={loop.name} loop={loop} nowMs={nowMs} />
          ))}
        </div>
      )}
    </section>
  );
}

function LoopCard({ loop, nowMs }: { loop: LoopHeartbeat; nowMs: number }) {
  const ageSec = heartbeatAgeSec(loop.last_heartbeat, nowMs);
  const stale = isHeartbeatStale(ageSec, loop.interval_sec);
  const status = loop.status.toLowerCase();

  return (
    <article
      className={cn(
        "rounded-xl border p-4 space-y-2",
        stale
          ? "border-danger/40 bg-danger-dim"
          : status === "ok" || status === "success"
            ? "border-up/40 bg-up/5"
            : status === "never"
              ? "border-border bg-surface-2"
              : "border-accent/40 bg-accent/5",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-sm font-semibold text-text">{loop.name}</p>
        <StatusBadge status={loop.status} stale={stale} />
      </div>

      <dl className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-muted-2">Heartbeat</dt>
          <dd
            className={cn(
              "mt-0.5 font-semibold tabular-nums",
              stale ? "text-danger" : "text-text",
            )}
          >
            {formatAgeSec(ageSec)}
            {stale ? " · stale" : ""}
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Interval</dt>
          <dd className="mt-0.5 font-mono tabular-nums text-text">
            {loop.interval_sec != null ? `${loop.interval_sec}s` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Planned</dt>
          <dd className="mt-0.5 text-text">{loop.planned ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt className="text-muted-2">Running</dt>
          <dd className="mt-0.5 text-text">{loop.running ? "yes" : "no"}</dd>
        </div>
      </dl>

      {loop.detail ? (
        <p className="truncate font-mono text-[11px] text-muted" title={loop.detail}>
          {loop.detail}
        </p>
      ) : null}
    </article>
  );
}

function StatusBadge({ status, stale }: { status: string; stale: boolean }) {
  const normalized = status.toLowerCase() || "unknown";
  if (stale) {
    return (
      <span className="rounded border border-danger/45 bg-danger-dim px-2 py-0.5 text-[10px] font-semibold uppercase text-danger">
        stale
      </span>
    );
  }
  const classes =
    normalized === "ok" || normalized === "success"
      ? "border-up/45 bg-up/10 text-up"
      : normalized === "never"
        ? "border-muted-2/40 bg-surface text-muted-2"
        : "border-accent/45 bg-accent/10 text-accent";

  return (
    <span className={cn("rounded border px-2 py-0.5 text-[10px] font-semibold uppercase", classes)}>
      {normalized}
    </span>
  );
}
