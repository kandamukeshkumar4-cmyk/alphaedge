"use client";

/**
 * DecisionCard — U03 "Bet / Pass / No-Edge" decision dashboard.
 *
 * Absorbs the AITakePanel data source (/explain) and adds:
 *  - Verdict chip: BET / PASS / NO-EDGE (derived from edge + CLV-gate status)
 *  - Model-vs-market probability bars
 *  - Edge % + CLV-gate status (amber provisional banner)
 *  - Mini calibration curve (CalibrationSparkline)
 *  - Collapsible rationale trace (RationaleTrace, from /agent-trace)
 *  - News + whale context chips
 *  - "Paper trading only" footer
 *
 * U08 ensemble extension (when ensemble flag ON):
 *  - "Models" row: per-model probability dots + labels
 *  - Disagreement/uncertainty band shown under model bars
 *  - All models labelled "provisional" until CLV gate passes
 *  - When flag OFF: single-model view is unchanged (no ensemble UI rendered)
 *
 * Data sources:
 *   GET /api/v1/markets/{slug}/explain    → model_prob, market_implied, edge,
 *                                           confidence_label, news_signals,
 *                                           trade_rationale, provisional,
 *                                           ensemble? (when flag ON)
 *   GET /api/v1/markets/{slug}/agent-trace → verdict, steps (rationale trace)
 *
 * GUARDRAIL: This component is advisory only. It has no order-submission
 * controls. The existing MarketTradingPanel keeps its own separate paper-order
 * flow and is not referenced here.
 */

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { pct } from "@/lib/mock-data";
import { API_BASE } from "@/lib/alphaedge-api";
import { CalibrationSparkline } from "./CalibrationSparkline";
import { RationaleTrace, type AgentTraceStep } from "./RationaleTrace";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type NewsSignal = {
  headline: string;
  sentiment_score: number;
  volume_score: number;
  sources_count: number;
};

// U08 — ensemble model estimate (present only when ensemble flag is ON)
type ModelEstimate = {
  model_id: string;
  probability: number;
  weight: number;
  source: string;
  provisional: boolean; // always true until CLV gate passes
};

type EnsembleData = {
  enabled: boolean;
  ensemble_prob: number;
  uncertainty_low: number;
  uncertainty_high: number;
  disagreement: number;
  model_estimates: ModelEstimate[];
  provisional: boolean;
  clv_gate_passed: boolean;
  notes: string;
};

type ExplainData = {
  slug: string;
  model_prob: number;
  market_implied: number;
  edge: number;
  edge_direction: string;
  confidence_label: string;
  news_signals: NewsSignal[];
  trade_rationale: string;
  provisional: boolean;
  paper_trading_only: boolean;
  // U08 — only present when ENSEMBLE_ENABLED=true
  ensemble?: EnsembleData;
};

type TraceData = {
  slug: string;
  verdict: "BET" | "PASS" | "NO-EDGE";
  provisional: boolean;
  approved: boolean;
  reasoning: string;
  steps: AgentTraceStep[];
  paper_trading_only: boolean;
};

// ---------------------------------------------------------------------------
// Verdict chip styles
// ---------------------------------------------------------------------------

function verdictChipClass(verdict: string): string {
  switch (verdict) {
    case "BET":
      return "border-primary/50 bg-primary/15 text-primary";
    case "PASS":
      return "border-border bg-surface-2 text-muted";
    case "NO-EDGE":
    default:
      return "border-amber-500/40 bg-amber-500/10 text-amber-300";
  }
}

function verdictLabel(verdict: string): string {
  switch (verdict) {
    case "BET":    return "BET";
    case "PASS":   return "PASS";
    default:       return "NO EDGE";
  }
}

// ---------------------------------------------------------------------------
// U08 — Ensemble models area (rendered only when ensemble flag is ON)
// ---------------------------------------------------------------------------

function EnsembleModelsSection({ data }: { data: EnsembleData }) {
  if (!data.enabled || data.model_estimates.length === 0) return null;

  const bandWidth = Math.round((data.uncertainty_high - data.uncertainty_low) * 100);
  const bandLeft = Math.round(data.uncertainty_low * 100);

  return (
    <div
      data-testid="ensemble-models-section"
      className="space-y-3 rounded-xl border border-border/60 bg-surface-2/50 px-3 py-3"
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wide text-muted">
          Models ({data.model_estimates.length})
        </span>
        {data.provisional && (
          <span
            data-testid="ensemble-provisional-label"
            className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300"
          >
            provisional
          </span>
        )}
      </div>

      {/* Per-model probability dots + labels */}
      <div className="space-y-1.5">
        {data.model_estimates.map((est) => (
          <div key={est.model_id} className="flex items-center gap-2">
            {/* probability dot on a 0-100% track */}
            <div className="relative h-1.5 flex-1 overflow-visible rounded-full bg-surface-2">
              <div
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-surface shadow"
                style={{ left: `${Math.round(est.probability * 100)}%` }}
                title={`${est.model_id}: ${(est.probability * 100).toFixed(1)}%`}
              />
            </div>
            <span className="w-14 text-right font-mono text-[11px] text-muted">
              {(est.probability * 100).toFixed(1)}%
            </span>
            <span className="w-20 truncate text-[10px] text-muted-2" title={est.model_id}>
              {est.model_id}
            </span>
          </div>
        ))}
      </div>

      {/* Disagreement / uncertainty band */}
      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-[10px] text-muted">Uncertainty band</span>
          <span className="font-mono text-[10px] text-muted">
            {(data.uncertainty_low * 100).toFixed(1)}%–{(data.uncertainty_high * 100).toFixed(1)}%
            {" "}(±{(data.disagreement * 100).toFixed(1)}% disagreement)
          </span>
        </div>
        <div className="relative h-2 overflow-hidden rounded-full bg-surface-2">
          {/* ensemble mean dot */}
          <div
            className="absolute top-0 h-full w-0.5 rounded-full bg-accent"
            style={{ left: `${Math.round(data.ensemble_prob * 100)}%` }}
          />
          {/* uncertainty band fill */}
          <div
            className="absolute top-0 h-full rounded-full bg-accent/25"
            style={{ left: `${bandLeft}%`, width: `${bandWidth}%` }}
          />
        </div>
      </div>

      {!data.clv_gate_passed && (
        <p className="text-[10px] text-muted-2">
          Flag ON · CLV gate not yet evaluated · all models provisional
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Props = {
  slug: string;
  className?: string;
};

export function DecisionCard({ slug, className }: Props) {
  const [explainData, setExplainData] = useState<ExplainData | null>(null);
  const [traceData, setTraceData] = useState<TraceData | null>(null);
  const [explainError, setExplainError] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [traceLoading, setTraceLoading] = useState(false);

  // Fetch /explain on mount
  useEffect(() => {
    if (!slug || !API_BASE) return;
    let cancelled = false;

    fetch(`${API_BASE}/api/v1/markets/${encodeURIComponent(slug)}/explain`)
      .then((r) => (r.ok ? (r.json() as Promise<ExplainData>) : Promise.reject()))
      .then((data) => { if (!cancelled) setExplainData(data); })
      .catch(() => { if (!cancelled) setExplainError(true); });

    return () => { cancelled = true; };
  }, [slug]);

  // Lazy-load /agent-trace when the trace section is opened
  const loadTrace = useCallback(() => {
    if (traceData || traceLoading || !API_BASE) return;
    setTraceLoading(true);
    fetch(`${API_BASE}/api/v1/markets/${encodeURIComponent(slug)}/agent-trace`)
      .then((r) => (r.ok ? (r.json() as Promise<TraceData>) : Promise.reject()))
      .then((data) => setTraceData(data))
      .catch(() => { /* silent: trace section shows empty state */ })
      .finally(() => setTraceLoading(false));
  }, [slug, traceData, traceLoading]);

  const handleTraceToggle = useCallback(() => {
    const nextOpen = !traceOpen;
    setTraceOpen(nextOpen);
    if (nextOpen) loadTrace();
  }, [traceOpen, loadTrace]);

  // Derive verdict: use trace if available (it's the canonical backend verdict);
  // fall back to a client-side heuristic from /explain while trace is loading.
  const verdict: string | null = (() => {
    if (traceData) return traceData.verdict;
    if (!explainData) return null;
    const mag = Math.abs(explainData.edge);
    if (mag < 0.02) return "NO-EDGE";
    if (mag >= 0.05 && !explainData.provisional) return "BET";
    return "PASS";
  })();

  // Loading skeleton
  if (!explainData && !explainError) {
    return (
      <section className={cn("rounded-2xl border border-border bg-surface p-4", className)}>
        <div className="space-y-3">
          <div className="skeleton h-7 w-32 rounded-full" />
          <div className="skeleton h-4 w-full rounded" />
          <div className="skeleton h-4 w-3/4 rounded" />
        </div>
      </section>
    );
  }

  // Error state
  if (explainError || !explainData) {
    return (
      <section className={cn("rounded-2xl border border-border bg-surface p-4", className)}>
        <p className="text-sm text-muted">AI advisor unavailable.</p>
        <p className="mt-1 text-xs text-muted-2">Paper trading only.</p>
      </section>
    );
  }

  const edgePct = (explainData.edge * 100).toFixed(1);
  const edgeSign = explainData.edge >= 0 ? "+" : "";

  return (
    <section className={cn("rounded-2xl border border-border bg-surface", className)}>
      {/* ── Header: verdict chip + title ── */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <h2 className="text-sm font-black uppercase tracking-wide text-text">
          Decision
        </h2>
        {verdict && (
          <span
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-black uppercase tracking-wider",
              verdictChipClass(verdict),
            )}
          >
            {verdictLabel(verdict)}
          </span>
        )}
      </div>

      <div className="space-y-4 border-t border-border px-4 pb-4 pt-4">
        {/* ── Provisional amber banner ── */}
        {explainData.provisional && (
          <p
            role="status"
            className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-200"
          >
            Provisional — model not yet CLV-validated
          </p>
        )}

        {/* ── Probability bars ── */}
        <div className="space-y-2">
          <div>
            <div className="mb-1 flex justify-between text-[11px] uppercase tracking-wide text-muted">
              <span>Model</span>
              <span>{pct(explainData.model_prob)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-accent"
                style={{ width: `${Math.round(explainData.model_prob * 100)}%` }}
              />
            </div>
          </div>

          <div>
            <div className="mb-1 flex justify-between text-[11px] uppercase tracking-wide text-muted">
              <span>Market</span>
              <span>{pct(explainData.market_implied)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round(explainData.market_implied * 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* ── U08 Ensemble models area (only when flag is ON) ── */}
        {explainData.ensemble?.enabled && (
          <EnsembleModelsSection data={explainData.ensemble} />
        )}

        {/* ── Edge + confidence + CLV label ── */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
          <span>
            Edge{" "}
            <span className={cn("font-mono font-bold", explainData.edge >= 0 ? "text-primary" : "text-danger")}>
              {edgeSign}{edgePct}%
            </span>
          </span>
          <span>
            Confidence{" "}
            <span className="font-semibold text-text">{explainData.confidence_label}</span>
          </span>
          <span>
            CLV gate{" "}
            <span className={cn("font-semibold", explainData.provisional ? "text-amber-300" : "text-primary")}>
              {explainData.provisional ? "provisional" : "validated"}
            </span>
          </span>
        </div>

        {/* ── Trade rationale ── */}
        <p className="text-sm leading-relaxed text-text">
          {explainData.trade_rationale}
        </p>

        {/* ── Mini calibration curve ── */}
        <CalibrationSparkline />

        {/* ── News + whale context chips ── */}
        {explainData.news_signals.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {explainData.news_signals.map((signal) => (
              <span
                key={signal.headline}
                className={cn(
                  "rounded-full border border-border bg-surface-2 px-2.5 py-1 text-[11px] text-muted",
                  signal.sentiment_score > 0.1 && "border-primary/30 text-primary",
                  signal.sentiment_score < -0.1 && "border-danger/30 text-danger",
                )}
              >
                {signal.headline.slice(0, 72)}
                {signal.headline.length > 72 ? "…" : ""}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-muted">News signals loading in background…</p>
        )}

        {/* ── Rationale trace (collapsible) ── */}
        <div className="rounded-xl border border-border">
          <button
            type="button"
            onClick={handleTraceToggle}
            aria-expanded={traceOpen}
            className="flex w-full items-center justify-between px-3 py-2 text-left"
          >
            <span className="text-xs font-bold text-text">Reasoning trace</span>
            <span className="text-[11px] text-muted">
              {traceOpen ? "Hide" : "Show"} agent steps
            </span>
          </button>

          {traceOpen && (
            <div className="border-t border-border px-3 py-3">
              {traceLoading && (
                <p className="text-[11px] text-muted">Loading trace…</p>
              )}
              {!traceLoading && traceData && (
                <RationaleTrace steps={traceData.steps} />
              )}
              {!traceLoading && !traceData && (
                <p className="text-[11px] text-muted">
                  Trace unavailable — backend may be offline.
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── Paper trading only footer ── */}
        <p className="text-center text-[11px] font-medium text-muted-2">
          Paper trading only — simulated funds, no real money
        </p>
      </div>
    </section>
  );
}
