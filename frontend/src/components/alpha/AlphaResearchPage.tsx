"use client";

import { useEffect, useState } from "react";

import {
  AlphaReportCard,
  AlphaReportCardSkeleton,
} from "@/components/alpha/AlphaReportCard";
import { FactorTable, FactorTableSkeleton } from "@/components/alpha/FactorTable";
import {
  HypothesesTable,
  HypothesesTableSkeleton,
} from "@/components/alpha/HypothesesTable";
import {
  LatestSignalCard,
  LatestSignalCardSkeleton,
} from "@/components/alpha/LatestSignalCard";
import {
  RunHistoryTable,
  RunHistoryTableSkeleton,
} from "@/components/alpha/RunHistoryTable";
import { PageHeader, PageShell, StatRow, StatTile } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import {
  ALPHA_CANONICAL_MARKET,
  fetchAlphaFactors,
  fetchAlphaReport,
  type AlphaFactors,
  type AlphaReport,
  type ApiSource,
} from "@/lib/alpha-api";
import {
  getHypotheses,
  getLatestSignal,
  getRuns,
  type AlphaRuns,
  type Hypotheses,
  type LatestSignal,
} from "@/lib/alpha-runs-api";

/*
 * Loop 99 AU2 — Multi-Factor Alpha research view (/alpha).
 * Loop 102 AR2 — Latest-signal hero + daily run history.
 * Loop 102 AR3 — Idea-generator hypotheses with validation verdicts.
 *
 * Factor scores + independent OOS validation for the canonical paper market,
 * beside the portfolio-wide validated-factor report. Paper-only: nothing
 * here touches the order path, and edge is displayed only for factors that
 * beat the closing line out-of-sample. Live API first; honest empty when a
 * source is absent. The badge is worst-of across ALL sources — any non-live
 * component means the page must not claim LIVE API.
 */

const PAPER_BANNER =
  "Paper-trading simulation · research output, not investment advice · simulated funds only";

function formatAsOf(asOf: string | null): string {
  if (!asOf) return "—";
  const ms = Date.parse(asOf);
  if (!Number.isFinite(ms)) return asOf;
  return new Date(ms).toISOString().slice(0, 16).replace("T", " ");
}

/** LIVE only when every known component is live; otherwise PAPER MOCK. */
function worstOfSources(sources: Array<ApiSource | null | undefined>): ApiSource | null {
  const known = sources.filter((s): s is ApiSource => s === "live" || s === "mock");
  if (known.length === 0) return null;
  return known.every((s) => s === "live") ? "live" : "mock";
}

export function AlphaResearchPage() {
  const [factors, setFactors] = useState<AlphaFactors | null>(null);
  const [report, setReport] = useState<AlphaReport | null>(null);
  const [factorsSource, setFactorsSource] = useState<ApiSource | null>(null);
  const [reportSource, setReportSource] = useState<ApiSource | null>(null);
  const [runsSource, setRunsSource] = useState<ApiSource | null>(null);
  const [signalSource, setSignalSource] = useState<ApiSource | null>(null);
  const [hypothesesSource, setHypothesesSource] = useState<ApiSource | null>(
    null,
  );
  const [loaded, setLoaded] = useState(false);
  const [runs, setRuns] = useState<AlphaRuns | null>(null);
  const [latestSignal, setLatestSignal] = useState<LatestSignal | null>(null);
  const [hypotheses, setHypotheses] = useState<Hypotheses | null>(null);
  const [tailLoaded, setTailLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      fetchAlphaFactors(ALPHA_CANONICAL_MARKET),
      fetchAlphaReport(),
    ]).then(([f, r]) => {
      if (cancelled) return;
      setFactors(f.data);
      setReport(r.data);
      setFactorsSource(f.source);
      setReportSource(r.source);
      setLoaded(true);
    });
    // Research tail (runs + latest signal + hypotheses) loads independently
    // so the hero and history are never blocked by the factor ledger.
    void Promise.all([getRuns(), getLatestSignal(), getHypotheses()]).then(
      ([h, s, p]) => {
        if (cancelled) return;
        setRuns(h.data);
        setLatestSignal(s.data);
        setHypotheses(p.data);
        setRunsSource(h.source);
        setSignalSource(s.source);
        setHypothesesSource(p.source);
        setTailLoaded(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const source = worstOfSources([
    factorsSource,
    reportSource,
    runsSource,
    signalSource,
    hypothesesSource,
  ]);

  const rows = factors?.factors ?? [];
  const validCount = rows.filter((f) => f.valid).length;
  const killedCount = rows.length - validCount;
  const survivorTStats = rows
    .filter((f) => f.valid && f.t_stat !== null)
    .map((f) => f.t_stat as number)
    .sort((a, b) => a - b);
  const medianT =
    survivorTStats.length === 0
      ? null
      : survivorTStats.length % 2 === 1
        ? survivorTStats[(survivorTStats.length - 1) / 2]!
        : (survivorTStats[survivorTStats.length / 2 - 1]! +
            survivorTStats[survivorTStats.length / 2]!) /
          2;

  return (
    <div data-testid="alpha-page" className="min-h-screen bg-bg">
      <PageShell width="wide">
        <PageHeader
          kicker="Multi-Factor Alpha · Phase 1"
          title="Multi-Factor Alpha"
          subtitle={
            <>
              Seven research signals scored for{" "}
              <span className="font-mono text-[13px] font-bold text-text">
                {ALPHA_CANONICAL_MARKET}
              </span>
              . Paper-only — a factor is shown as an edge only if it beats the
              closing line out-of-sample, judged by an independent validator.
            </>
          }
          actions={
            <div className="flex flex-col items-start gap-1.5 sm:items-end">
              <span
                data-testid="alpha-source-badge"
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] font-black tracking-[0.12em]",
                  source === "live"
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border bg-surface-2 text-muted",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    source === "live" ? "bg-primary" : "bg-muted-2",
                  )}
                />
                {source === "live" ? "LIVE API" : "PAPER MOCK"}
              </span>
              <span className="font-mono text-[11px] tabular-nums text-muted-2">
                as of {formatAsOf(factors?.as_of ?? null)} UTC
              </span>
            </div>
          }
        />

        <div
          data-testid="alpha-paper-banner"
          className="mb-6 flex items-center gap-2.5 rounded-xl border border-border bg-surface-2/70 px-3.5 py-2.5"
        >
          <span className="rounded border border-primary/30 bg-primary-dim/60 px-1.5 py-0.5 font-mono text-[9px] font-black uppercase tracking-[0.14em] text-primary">
            Sim
          </span>
          <p className="text-[12px] font-medium text-muted">{PAPER_BANNER}</p>
        </div>

        <div className="mb-6">
          {tailLoaded && latestSignal ? (
            <LatestSignalCard signal={latestSignal} />
          ) : (
            <LatestSignalCardSkeleton />
          )}
        </div>

        {loaded ? (
          <>
            <StatRow cols={4} className="mb-6">
              <StatTile
                label="Valid factors"
                value={`${validCount}/${rows.length}`}
                hint="survive OOS validation"
                accent={validCount > 0}
              />
              <StatTile
                label="Killed"
                value={String(killedCount)}
                hint="failed the validator — shown gray, not red"
              />
              <StatTile
                label="Median t · survivors"
                value={medianT === null ? "—" : medianT.toFixed(2)}
                hint="Newey-West HAC"
              />
              <StatTile
                label="Market"
                value={
                  <span className="text-sm leading-tight">{ALPHA_CANONICAL_MARKET}</span>
                }
                hint="canonical paper market"
              />
            </StatRow>

            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
              <FactorTable factors={factors} market={ALPHA_CANONICAL_MARKET} />
              <AlphaReportCard report={report} />
            </div>

            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              {tailLoaded ? (
                <>
                  <RunHistoryTable runs={runs} />
                  <HypothesesTable hypotheses={hypotheses} />
                </>
              ) : (
                <>
                  <RunHistoryTableSkeleton />
                  <HypothesesTableSkeleton />
                </>
              )}
            </div>

            <p className="mt-6 font-mono text-[11px] leading-relaxed text-muted-2">
              factors: loop96 seven-factor graph · validator: chronological OOS
              split, block-bootstrap CI, Newey-West HAC t, OOS-degradation cap ·
              a signal is emitted only when the residual alpha beats the
              closing line out-of-sample · PAPER_TRADING_ONLY=true
            </p>
          </>
        ) : (
          <>
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
              <FactorTableSkeleton />
              <AlphaReportCardSkeleton />
            </div>
            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              <RunHistoryTableSkeleton />
              <HypothesesTableSkeleton />
            </div>
          </>
        )}
      </PageShell>
    </div>
  );
}
