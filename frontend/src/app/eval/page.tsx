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
 *
 * P06: re-themed from leftover slate/admin styling to Quest mint-on-charcoal
 * tokens. Honesty about unmeasured ensemble flags is preserved verbatim.
 */

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { PageHeader, PageShell } from "@/components/ui/kit";
import { DriftSeriesPanel } from "@/components/DriftSeriesPanel";
import { ModelAbCard } from "@/components/ModelAbCard";
import { ModelRegistryPanel } from "@/components/ModelRegistryPanel";
import { PopulationCompositionPanel } from "@/components/PopulationCompositionPanel";
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

function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <dt className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{label}</dt>
      <dd className="mt-1 font-mono text-xl font-bold text-text">{value}</dd>
    </div>
  );
}

export default function EvalDashboard() {
  const [aggregates, setAggregates] = useState<EvalAggregates | null>(null);
  const [autolab, setAutolab] = useState<AutoLabMeasurement | null>(null);
  const [unavailable, setUnavailable] = useState(false);

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
      notes: "Ensemble comparison has not been run yet.",
    };
    fetch(`${API}/api/v1/ensemble/autolab`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data) => setAutolab(data as AutoLabMeasurement))
      .catch(() => setUnavailable(true));
  }, []);

  const ensembleBetter =
    autolab?.ensemble_brier != null &&
    autolab?.baseline_brier != null &&
    autolab.ensemble_brier < autolab.baseline_brier;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Model proof"
        title="Proof dashboard"
        subtitle="Brier · calibration · backtest summary. Research only — paper trading, simulated funds."
      />

      {/* ── Single-model eval aggregates ── */}
      {aggregates ? (
        <dl className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatCard label="Mean Brier (7d)" value={aggregates.mean_brier?.toFixed(4) ?? "—"} />
          <StatCard
            label="Calibration error"
            value={aggregates.calibration_error?.toFixed(4) ?? "—"}
          />
          <StatCard label="Markets evaluated" value={aggregates.market_count ?? 0} />
        </dl>
      ) : (
        <p className="mt-4 rounded-xl border border-gold/30 bg-gold/10 px-4 py-3 text-sm font-semibold text-gold">
          Start the API to load eval metrics.
        </p>
      )}

      {/* ── U08 Ensemble vs single-model Brier comparison ── */}
      <section data-testid="ensemble-autolab-section" className="mt-10">
        <h2 className="text-lg font-black text-text">Ensemble vs single-model (U08 AutoLab)</h2>
        <p className="mt-1 text-sm text-muted">
          Walk-forward Brier comparison — ensemble flag is{" "}
          {autolab?.ensemble_enabled ? (
            <span className="font-bold text-primary">ON</span>
          ) : (
            <span className="font-bold text-gold">OFF (default)</span>
          )}
          . Flag only turns ON when ensemble Brier is measurably lower than baseline.
        </p>

        {autolab === null && !unavailable ? (
          <p className="mt-4 text-sm text-muted-2">Loading…</p>
        ) : unavailable ? (
          <div
            data-testid="ensemble-unavailable"
            className="mt-4 rounded-2xl border border-muted/30 bg-muted/10 p-4"
          >
            <p className="text-sm font-medium text-text">
              Ensemble AutoLab: not yet measured. This section will populate when
              the ensemble evaluation pipeline ships.
            </p>
          </div>
        ) : autolab && (autolab.outcome === "not_run" || autolab.outcome === "insufficient_data") ? (
          /* Honest "not yet measured" state — never fabricate bars */
          <div
            data-testid="ensemble-not-measured"
            className="mt-4 rounded-2xl border border-gold/30 bg-gold/10 p-4"
          >
            <p className="text-sm font-bold text-gold">
              {autolab.outcome === "not_run"
                ? "Not yet measured"
                : `Insufficient data (${autolab.n_samples} resolved markets; need ≥30)`}
            </p>
            <p className="mt-1 text-xs text-muted">
              {autolab.outcome === "not_run"
                ? "Ensemble comparison stays off until a walk-forward Brier run beats the single-model baseline. No fabricated scores."
                : autolab.notes}
            </p>
          </div>
        ) : (
          /* Real numbers — outcome === "measured" (guaranteed by elimination) */
          <div data-testid="ensemble-measured" className="mt-4 space-y-4">
            <dl className="grid grid-cols-2 gap-3">
              <StatCard
                label="Single-model Brier"
                value={autolab!.baseline_brier?.toFixed(4) ?? "—"}
              />
              <div className="rounded-2xl border border-border bg-surface p-4">
                <dt className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
                  Ensemble Brier
                </dt>
                <dd
                  className={cn(
                    "mt-1 font-mono text-xl font-bold",
                    ensembleBetter ? "text-up" : "text-danger",
                  )}
                >
                  {autolab!.ensemble_brier?.toFixed(4) ?? "—"}
                </dd>
              </div>
              <StatCard label="Resolved markets (n)" value={autolab!.n_samples} />
              <StatCard
                label="Improvement"
                value={
                  autolab!.ensemble_brier !== null && autolab!.baseline_brier !== null
                    ? `${((autolab!.baseline_brier - autolab!.ensemble_brier) * 100).toFixed(2)}pp`
                    : "—"
                }
              />
            </dl>
            <p className="text-xs text-muted-2">{autolab!.notes}</p>
          </div>
        )}
      </section>

      {/* ── W03 LightGBM-vs-XGBoost walk-forward A/B readout ── */}
      <ModelAbCard />
      <PopulationCompositionPanel />
      <DriftSeriesPanel />
      <ModelRegistryPanel />
    </PageShell>
  );
}
