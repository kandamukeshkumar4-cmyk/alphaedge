"use client";

// O2 — Source health board on /admin/observability.
// Admin-gated GET /api/v1/system/sources; key from React memory only
// (useAdminApiKey / AdminKeyProvider — never persisted here).

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  fetchSystemSources,
  type SourceHealthRow,
} from "@/lib/admin-dashboard-api";
import { formatAgeSec } from "@/lib/observability-api";
import { useAdminApiKey } from "@/lib/admin-context";

export function SourceHealthBoard() {
  const apiKey = useAdminApiKey();
  const [sources, setSources] = useState<SourceHealthRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!apiKey.trim()) {
      setSources([]);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const result = await fetchSystemSources(apiKey);
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setSources([]);
      return;
    }
    setError(null);
    setSources(result.data.sources);
  }, [apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="rounded-xl border border-border bg-surface" id="source-health">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text">Source health</h2>
          <p className="text-xs text-muted">
            Connector circuit breakers — open breakers render in red.
          </p>
        </div>
        <button
          className="rounded border border-border-light px-3 py-1 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:opacity-50"
          disabled={loading || !apiKey.trim()}
          onClick={() => void load()}
          type="button"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {!apiKey.trim() ? (
        <p className="p-4 text-sm text-muted">
          Enter the admin API key above to load connector source health.
        </p>
      ) : error ? (
        <p role="alert" className="p-4 text-sm text-danger">
          {error}
        </p>
      ) : loading && sources.length === 0 ? (
        <p className="p-4 text-sm text-muted">Loading source health…</p>
      ) : sources.length === 0 ? (
        <p className="p-4 text-sm text-muted">No connector sources reported.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
          {sources.map((row) => (
            <SourceCard key={row.source} row={row} />
          ))}
        </div>
      )}
    </section>
  );
}

function SourceCard({ row }: { row: SourceHealthRow }) {
  const state = row.state.toLowerCase();
  const isOpen = state === "open";

  return (
    <article
      className={cn(
        "rounded-xl border p-4 space-y-2",
        isOpen
          ? "border-danger/40 bg-danger-dim"
          : state === "degraded"
            ? "border-accent/40 bg-accent/5"
            : state === "healthy"
              ? "border-up/40 bg-up/5"
              : "border-border bg-surface-2",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-sm font-semibold text-text">{row.source}</p>
        <span
          className={cn(
            "rounded border px-2 py-0.5 text-[10px] font-semibold uppercase",
            isOpen
              ? "border-danger/45 bg-danger-dim text-danger"
              : state === "degraded"
                ? "border-accent/45 bg-accent/10 text-accent"
                : state === "healthy"
                  ? "border-up/45 bg-up/10 text-up"
                  : "border-muted-2/40 bg-surface text-muted-2",
          )}
        >
          {state || "unknown"}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-muted-2">Successes</dt>
          <dd className="mt-0.5 font-mono tabular-nums text-text">
            {row.total_successes.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Failures</dt>
          <dd className="mt-0.5 font-mono tabular-nums text-text">
            {row.total_failures.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Last success</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-text">
            {formatAgeSec(
              row.last_success_age_sec != null
                ? Math.floor(row.last_success_age_sec)
                : null,
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Consecutive fails</dt>
          <dd className="mt-0.5 font-mono tabular-nums text-text">
            {row.consecutive_failures}
          </dd>
        </div>
      </dl>

      {isOpen && row.circuit_open_remaining_sec != null ? (
        <p className="text-xs font-semibold text-danger">
          Circuit open · {Math.ceil(row.circuit_open_remaining_sec)}s remaining
        </p>
      ) : null}

      {row.last_error ? (
        <p className="truncate font-mono text-[11px] text-muted" title={row.last_error}>
          {row.last_error}
        </p>
      ) : null}
    </article>
  );
}
