"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { fetchModelRegistry, type ModelRegistryResponse } from "@/lib/eval-api";

export function ModelRegistryPanel() {
  const [apiKey, setApiKey] = useState("");
  const [draftKey, setDraftKey] = useState("");
  const [data, setData] = useState<ModelRegistryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!apiKey.trim()) return;
    setLoading(true);
    const result = await fetchModelRegistry(apiKey);
    setLoading(false);
    if (!result) {
      setError("Model registry unavailable or the admin key was rejected.");
      setData(null);
      return;
    }
    setError(null);
    setData(result);
  }, [apiKey]);

  useEffect(() => {
    if (apiKey) void load();
  }, [apiKey, load]);

  function saveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextKey = draftKey.trim();
    if (!nextKey) return;
    setApiKey(nextKey);
  }

  function clearKey() {
    setApiKey("");
    setDraftKey("");
    setData(null);
    setError(null);
  }

  return (
    <section className="mt-10 rounded-2xl border border-border bg-surface" data-testid="model-registry-panel">
      <header className="border-b border-border px-4 py-4">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-primary">Admin-only view</p>
        <h2 className="mt-1 text-lg font-black text-text">Model registry</h2>
        <p className="mt-1 text-sm text-muted">
          Persisted versions, training-data hashes, and recorded Brier/calibration metrics. The key is held in memory only.
        </p>
      </header>

      {!apiKey ? (
        <form className="flex flex-col gap-2 p-4 sm:flex-row" onSubmit={saveKey}>
          <label className="sr-only" htmlFor="eval-admin-api-key">Admin API key</label>
          <input
            id="eval-admin-api-key"
            type="password"
            autoComplete="off"
            value={draftKey}
            onChange={(event) => setDraftKey(event.target.value)}
            placeholder="X-Admin-API-Key"
            className="min-h-11 min-w-0 flex-1 rounded-xl border border-border bg-bg px-3 font-mono text-sm text-text outline-none focus:border-accent"
          />
          <button type="submit" disabled={!draftKey.trim()} className="min-h-11 rounded-xl bg-accent px-4 text-sm font-black text-bg transition hover:brightness-110 disabled:opacity-50">
            Load registry
          </button>
        </form>
      ) : (
        <section className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <p className="text-xs text-muted">Admin key is active for this page session only.</p>
          <section className="flex gap-2">
            <button type="button" onClick={() => void load()} disabled={loading} className="min-h-9 rounded-lg border border-border-light px-3 text-xs font-bold text-muted hover:border-primary hover:text-primary disabled:opacity-50">
              {loading ? "Loading…" : "Refresh"}
            </button>
            <button type="button" onClick={clearKey} className="min-h-9 rounded-lg border border-danger/40 px-3 text-xs font-bold text-danger hover:border-danger">
              Clear key
            </button>
          </section>
        </section>
      )}

      {error ? <p role="alert" className="mx-4 my-4 rounded-lg border border-danger/30 bg-danger-dim px-3 py-2 text-sm text-danger">{error}</p> : null}
      {data ? (
        data.models.length === 0 ? (
          <p className="p-4 text-sm text-muted">No model versions have been registered yet.</p>
        ) : (
          <section className="overflow-x-auto p-4">
            <table className="w-full min-w-[760px] text-left text-xs">
              <caption className="sr-only">Registered model versions</caption>
              <thead className="border-b border-border text-[10px] uppercase tracking-[0.08em] text-muted-2">
                <tr><th className="px-2 py-2 font-bold">Model</th><th className="px-2 py-2 font-bold">Version</th><th className="px-2 py-2 font-bold">Brier</th><th className="px-2 py-2 font-bold">Calibration</th><th className="px-2 py-2 font-bold">Training hash</th><th className="px-2 py-2 font-bold">State</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.models.map((model) => (
                  <tr key={model.id}>
                    <td className="px-2 py-3 font-semibold text-text">{model.name}</td>
                    <td className="px-2 py-3 font-mono text-muted">{model.version}</td>
                    <td className="px-2 py-3 font-mono tabular-nums text-muted">{formatMetric(model.metrics.brier)}</td>
                    <td className="px-2 py-3 font-mono tabular-nums text-muted">{formatMetric(model.metrics.calibration ?? model.metrics.expected_calibration_error)}</td>
                    <td className="max-w-52 truncate px-2 py-3 font-mono text-muted-2" title={model.training_data_hash ?? undefined}>{model.training_data_hash ?? "—"}</td>
                    <td className="px-2 py-3">{model.is_active ? <span className="rounded border border-primary/30 bg-primary-dim px-2 py-1 font-bold text-primary">Active</span> : <span className="text-muted-2">Archived</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )
      ) : !loading && !error && apiKey ? (
        <p className="p-4 text-sm text-muted">Enter a valid admin key to load model versions.</p>
      ) : null}
    </section>
  );
}

function formatMetric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
}
