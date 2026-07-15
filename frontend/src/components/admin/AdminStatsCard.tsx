"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchAdminStats, type AdminStats } from "@/lib/admin-dashboard-api";

export function AdminStatsCard({ apiKey }: { apiKey: string }) {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!apiKey.trim()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const result = await fetchAdminStats(apiKey);
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setStats(null);
      return;
    }
    setError(null);
    setStats(result.data);
  }, [apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="rounded-xl border border-border bg-surface p-5" id="stats">
      <header className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-black text-text">System stats</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading || !apiKey}
          className="min-h-9 rounded-lg border border-border-light px-3 text-xs font-bold text-muted transition hover:border-primary hover:text-primary disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </header>
      {error ? (
        <p role="alert" className="mt-3 rounded-lg border border-danger/30 bg-danger-dim px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {stats ? (
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Users" value={stats.users} />
          <Stat label="Open markets" value={stats.markets_by_status.open} />
          <Stat label="Trades · 24h" value={stats.trades.last_24h} />
          <Stat label="Trades · 7d" value={stats.trades.last_7d} />
          <Stat label="Forecasts locked" value={stats.forecasts.locked} />
          <Stat label="Forecasts graded" value={stats.forecasts.graded} />
          <Stat label="Resolved markets" value={stats.markets_by_status.resolved} />
          <Stat label="Cancelled markets" value={stats.markets_by_status.cancelled} />
        </dl>
      ) : !loading && !error ? (
        <p className="mt-3 text-sm text-muted">Enter the admin key above to load system stats.</p>
      ) : null}
      {stats ? (
        <p className="mt-3 text-xs text-muted-2">
          Generated {new Date(stats.generated_at).toLocaleString()} · cached {stats.cached ? "yes" : "no"}
        </p>
      ) : null}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <article className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
      <dt className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">{label}</dt>
      <dd className="mt-1 font-mono text-lg font-black tabular-nums text-text">{value.toLocaleString()}</dd>
    </article>
  );
}
