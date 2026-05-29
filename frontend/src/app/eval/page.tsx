"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function EvalDashboard() {
  const [aggregates, setAggregates] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/eval/aggregates`)
      .then((r) => r.json())
      .then(setAggregates)
      .catch(() => setAggregates(null));
  }, []);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">Proof Dashboard</h1>
      <p className="text-sm text-slate-400">Brier · calibration · backtest summary</p>
      {aggregates ? (
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div className="rounded border border-slate-800 p-4">
            <dt className="text-slate-500">Mean Brier (7d)</dt>
            <dd className="text-xl">{aggregates.mean_brier?.toFixed(4) ?? "—"}</dd>
          </div>
          <div className="rounded border border-slate-800 p-4">
            <dt className="text-slate-500">Calibration error</dt>
            <dd className="text-xl">{aggregates.calibration_error?.toFixed(4) ?? "—"}</dd>
          </div>
          <div className="rounded border border-slate-800 p-4">
            <dt className="text-slate-500">Markets evaluated</dt>
            <dd className="text-xl">{aggregates.market_count ?? 0}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-6 text-amber-400">Start API to load eval metrics.</p>
      )}
    </main>
  );
}
