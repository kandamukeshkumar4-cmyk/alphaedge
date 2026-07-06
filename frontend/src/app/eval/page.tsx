"use client";

/**
 * Eval / Proof Dashboard — U03 calibration + U08 ensemble vs single comparison.
 *
 * U08 section: shows the real ensemble vs single-model Brier numbers from the
 * AutoLab harness, OR an honest "not yet measured" state when:
 *   - ENSEMBLE_ENABLED is false (flag is OFF — default)
 *   - fewer than 30 resolved markets are available for walk-forward measurement
 *
 * GUARDRAIL: Never fabricates Brier numbers. The "not yet measured" state is
 * the honest correct state when the AutoLab gate has not been run.
 */

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
const API = API_BASE;

type EvalAggregates = Record<string, number>;

// U08 — AutoLab measurement result from /api/v1/ensemble/autolab
type AutoLabMeasurement = {
  ensemble_enabled: boolean;
  outcome: "insufficient_data" | "measured" | "not_run";
  baseline_brier: number | null;
  ensemble_brier: number | null;
  n_samples: number;
  notes: string;
};

export default function EvalDashboard() {
  const [aggregates, setAggregates] = useState<EvalAggregates | null>(null);
  const [autolab, setAutolab] = useState<AutoLabMeasurement | null>(null);

  useEffect(() => {
    if (!API) return;

    fetch(`${API}/api/v1/eval/aggregates`)
      .then((r) => r.json())
      .then(setAggregates)
      .catch(() => setAggregates(null));

    // U08 — fetch ensemble AutoLab result; fail gracefully (endpoint is optional).
    // A non-OK response (endpoint not wired → 404) must ALSO land in the honest
    // "not yet measured" state — not only network rejections — otherwise the
    // section is stuck on "Loading…" forever.
    const notRun: AutoLabMeasurement = {
      ensemble_enabled: false,
      outcome: "not_run",
      baseline_brier: null,
      ensemble_brier: null,
      n_samples: 0,
      notes: "AutoLab endpoint not yet available. ENSEMBLE_ENABLED=false (default).",
    };
    fetch(`${API}/api/v1/ensemble/autolab`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setAutolab(data ? (data as AutoLabMeasurement) : notRun))
      .catch(() => setAutolab(notRun));
  }, []);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">Proof Dashboard</h1>
      <p className="text-sm text-slate-400">Brier · calibration · backtest summary</p>

      {/* ── Single-model eval aggregates ── */}
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

      {/* ── U08 Ensemble vs single-model Brier comparison ── */}
      <section
        data-testid="ensemble-autolab-section"
        className="mt-10"
      >
        <h2 className="text-lg font-bold">Ensemble vs Single-Model (U08 AutoLab)</h2>
        <p className="mt-1 text-sm text-slate-400">
          Walk-forward Brier comparison — ensemble flag is{" "}
          {autolab?.ensemble_enabled ? (
            <span className="font-bold text-green-400">ON</span>
          ) : (
            <span className="font-bold text-amber-400">OFF (default)</span>
          )}
          . Flag only turns ON when ensemble Brier is measurably lower than baseline.
        </p>

        {autolab === null ? (
          <p className="mt-4 text-sm text-slate-500">Loading…</p>
        ) : autolab.outcome === "not_run" || autolab.outcome === "insufficient_data" ? (
          /* Honest "not yet measured" state — never fabricate bars */
          <div
            data-testid="ensemble-not-measured"
            className="mt-4 rounded border border-amber-800/40 bg-amber-950/30 p-4"
          >
            <p className="text-sm font-semibold text-amber-300">
              {autolab.outcome === "not_run"
                ? "Not yet measured"
                : `Insufficient data (${autolab.n_samples} resolved markets; need ≥30)`}
            </p>
            <p className="mt-1 text-xs text-slate-400">{autolab.notes}</p>
            <p className="mt-2 text-xs text-slate-500">
              AutoLab line: baseline=single-model | benchmark=walk-forward Brier |
              iterations=0 | budget=0/8 | outcome=stalled-iterations=0-honest
            </p>
          </div>
        ) : (
          /* Real numbers — outcome === "measured" */
          <div
            data-testid="ensemble-measured"
            className="mt-4 space-y-4"
          >
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div className="rounded border border-slate-800 p-4">
                <dt className="text-slate-500">Single-model Brier</dt>
                <dd className="text-xl font-mono">
                  {autolab.baseline_brier?.toFixed(4) ?? "—"}
                </dd>
              </div>
              <div className="rounded border border-slate-800 p-4">
                <dt className="text-slate-500">Ensemble Brier</dt>
                <dd
                  className={[
                    "text-xl font-mono",
                    autolab.ensemble_brier !== null &&
                    autolab.baseline_brier !== null &&
                    autolab.ensemble_brier < autolab.baseline_brier
                      ? "text-green-400"
                      : "text-red-400",
                  ].join(" ")}
                >
                  {autolab.ensemble_brier?.toFixed(4) ?? "—"}
                </dd>
              </div>
              <div className="rounded border border-slate-800 p-4">
                <dt className="text-slate-500">Resolved markets (n)</dt>
                <dd className="text-xl">{autolab.n_samples}</dd>
              </div>
              <div className="rounded border border-slate-800 p-4">
                <dt className="text-slate-500">Improvement</dt>
                <dd className="text-xl font-mono">
                  {autolab.ensemble_brier !== null && autolab.baseline_brier !== null
                    ? ((autolab.baseline_brier - autolab.ensemble_brier) * 100).toFixed(2) + "pp"
                    : "—"}
                </dd>
              </div>
            </dl>
            <p className="text-xs text-slate-500">{autolab.notes}</p>
          </div>
        )}
      </section>
    </main>
  );
}
