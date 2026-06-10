"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchAdminJobs, type AdminJobRun } from "@/lib/admin-dashboard-api";

type SystemHealthCardProps = {
  apiKey: string;
};

export function SystemHealthCard({ apiKey }: SystemHealthCardProps) {
  const [runs, setRuns] = useState<AdminJobRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    if (!apiKey.trim()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const result = await fetchAdminJobs(apiKey, 5);
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setRuns([]);
      return;
    }
    setRuns(result.data.runs);
  }, [apiKey]);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  return (
    <section className="rounded-xl border border-border bg-surface" id="jobs">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text">Job Health</h2>
        <button
          className="rounded border border-border-light px-3 py-1 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:opacity-50"
          disabled={loading}
          onClick={() => void loadJobs()}
          type="button"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error ? (
        <p className="p-4 text-sm text-danger">{error}</p>
      ) : loading ? (
        <p className="p-4 text-sm text-muted">Loading job runs…</p>
      ) : runs.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-border bg-surface-2 text-xs uppercase text-muted-2">
              <tr>
                <th className="px-4 py-3 font-semibold">Job</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Timestamp</th>
                <th className="px-4 py-3 font-semibold">Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {runs.map((run) => (
                <tr key={`${run.job_name}-${run.started_at}`}>
                  <td className="px-4 py-3 font-mono text-xs text-text">{run.job_name}</td>
                  <td className="px-4 py-3">
                    <JobStatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-muted">{formatDate(run.started_at)}</td>
                  <td className="px-4 py-3">
                    <pre className="max-h-24 max-w-md overflow-auto whitespace-pre-wrap break-words rounded bg-bg/65 p-2 font-mono text-xs text-muted">
                      {JSON.stringify(run.summary, null, 2)}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="p-4 text-sm text-muted">No job runs recorded.</p>
      )}
    </section>
  );
}

function JobStatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const classes =
    normalized === "success"
      ? "border-primary/45 bg-primary-dim text-primary"
      : normalized === "degraded"
        ? "border-accent/45 bg-accent/10 text-accent"
        : "border-danger/45 bg-danger-dim text-danger";

  return (
    <span className={cn("inline-flex rounded border px-2 py-1 text-xs font-semibold", classes)}>
      {normalized || "unknown"}
    </span>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
