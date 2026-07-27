"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ChartAttribution } from "@/components/ChartAttribution";
import { cn } from "@/lib/cn";
import { observeChartTheme, readLwcChartTheme } from "@/lib/chart-colors";
import {
  getRunArtifact,
  type ArtifactMatch,
  type ScannerRunArtifact,
} from "@/lib/scanners-api";

/*
 * Loop116 — the fired-alert dashboard artifact (VIDEO-PARITY-AUDIT gap #2).
 *
 * When a scanner run finishes, the backend assembles a rendered DOCUMENT and
 * this component draws it: headline + FIRED/NO-FIRE pill, KPI tiles, the
 * per-step funnel, the matched-markets table, one chart, and the two narrative
 * sections. It renders ABOVE the existing step list — it never replaces it.
 *
 * Every narrative sentence is plain DOM text (crawlable, selectable, readable
 * by a screen reader), not an image. Research-only by backend contract: the
 * "What to do now" list carries research actions, never a trade instruction.
 */

// ---------------------------------------------------------------------------
// Chart — lightweight-charts histogram, one column per matched market.
// ---------------------------------------------------------------------------

/**
 * The app's chart library is time-indexed, and matched markets are categorical,
 * so the time scale is hidden and the market names live in the DOM legend
 * beneath the canvas. Nothing on the canvas claims to be a date.
 */
function ArtifactBarChart({
  series,
  valueLabel,
}: {
  series: { label: string; market_slug: string; value: number }[];
  valueLabel: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || series.length === 0) return;
    let disposed = false;
    let cleanup: (() => void) | undefined;

    void (async () => {
      const { ColorType, createChart, HistogramSeries } = await import(
        "lightweight-charts"
      );
      if (disposed || !hostRef.current) return;

      const theme = readLwcChartTheme();
      const chart = createChart(host, {
        width: host.clientWidth || 640,
        height: 200,
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: theme.text,
          attributionLogo: false,
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { color: theme.grid },
        },
        rightPriceScale: { borderColor: theme.border },
        // Categorical data: the x axis carries no meaning, so it is hidden.
        timeScale: { visible: false, borderColor: theme.border },
        handleScroll: false,
        handleScale: false,
        crosshair: { horzLine: { labelVisible: false }, vertLine: { visible: false } },
      });

      const column = chart.addSeries(HistogramSeries, {
        color: theme.accent,
        base: 0,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // Index positions only — never rendered as dates (time scale is hidden).
      column.setData(
        series.map((point, index) => ({
          time: (index + 1) as never,
          value: point.value,
        })),
      );
      chart.timeScale().fitContent();

      const resize = new ResizeObserver(() => {
        chart.applyOptions({ width: host.clientWidth });
      });
      resize.observe(host);

      const observer = observeChartTheme(() => {
        const next = readLwcChartTheme();
        chart.applyOptions({
          layout: { textColor: next.text },
          grid: { horzLines: { color: next.grid } },
          rightPriceScale: { borderColor: next.border },
        });
        column.applyOptions({ color: next.accent });
      });

      cleanup = () => {
        resize.disconnect();
        observer?.disconnect();
        chart.remove();
      };
    })();

    return () => {
      disposed = true;
      cleanup?.();
    };
  }, [series]);

  if (series.length === 0) return null;

  return (
    <div className="space-y-2">
      <div
        ref={hostRef}
        role="img"
        aria-label={`Bar chart: ${valueLabel} for ${series.length} matched market${series.length === 1 ? "" : "s"}`}
        data-testid="artifact-chart"
        className="h-[200px] w-full rounded-lg border border-border bg-bg/55"
      />
      <ol
        data-testid="artifact-chart-legend"
        className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-muted"
      >
        {series.map((point, index) => (
          <li key={point.market_slug || point.label} className="flex items-center gap-1.5">
            <span className="text-muted-2 tabular-nums">{index + 1}.</span>
            <span className="truncate max-w-[16rem] text-text">{point.label}</span>
            <span className="tabular-nums text-primary">{point.value.toFixed(2)}</span>
          </li>
        ))}
      </ol>
      <ChartAttribution />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

function FiredPill({ fired }: { fired: boolean }) {
  return (
    <span
      data-testid="artifact-fired-pill"
      data-fired={fired ? "true" : "false"}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[10.5px] font-black uppercase tracking-[0.14em]",
        fired
          ? "border-primary/40 bg-primary/12 text-primary"
          : "border-border bg-surface-2/60 text-muted",
      )}
    >
      <span
        aria-hidden
        className={cn("h-1.5 w-1.5 rounded-full", fired ? "bg-primary" : "bg-muted-2")}
      />
      {fired ? "fired" : "no fire"}
    </span>
  );
}

function KpiTile({
  label,
  value,
  delta,
}: {
  label: string;
  value: string | number;
  delta?: number;
}) {
  const deltaLabel =
    typeof delta === "number" && delta !== 0
      ? `${delta > 0 ? "+" : ""}${delta} vs last run`
      : null;
  return (
    <div className="min-w-0 rounded-lg border border-border bg-bg/55 px-3 py-2.5">
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
        {label}
      </div>
      <div className="mt-1 truncate text-lg font-black tracking-tight text-text tabular-nums">
        {value}
      </div>
      {deltaLabel ? (
        <div
          className={cn(
            "mt-0.5 font-mono text-[10.5px] font-bold",
            delta && delta > 0 ? "text-primary" : "text-muted",
          )}
        >
          {deltaLabel}
        </div>
      ) : null}
    </div>
  );
}

function priceLabel(price: number | null): string {
  return price === null ? "—" : `${Math.round(price * 100)}¢`;
}

function volumeLabel(volume: number | null): string {
  if (volume === null) return "—";
  if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`;
  if (volume >= 1_000) return `${(volume / 1_000).toFixed(1)}K`;
  return String(volume);
}

function lockLabel(lockAt: string | null): string {
  if (!lockAt) return "—";
  const at = new Date(lockAt);
  if (Number.isNaN(at.getTime())) return "—";
  const hours = (at.getTime() - Date.now()) / 3_600_000;
  if (hours < 0) return "locked";
  if (hours < 1) return `${Math.max(Math.round(hours * 60), 1)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

/** Compact per-step read summary for one matched market row. */
function scoreChips(match: ArtifactMatch): { key: string; text: string }[] {
  const out: { key: string; text: string }[] = [];
  for (const [step, raw] of Object.entries(match.scores ?? {})) {
    const fields = raw ?? {};
    const parts: string[] = [];
    const dir = fields.direction;
    if (dir === "up" || dir === "down") parts.push(dir === "up" ? "↑" : "↓");
    for (const key of ["edge", "abs_gap", "pressure", "sentiment_score", "change", "hours_to_lock"]) {
      const value = fields[key];
      if (typeof value === "number" && Number.isFinite(value)) {
        parts.push(`${key} ${value.toFixed(key === "hours_to_lock" ? 1 : 3)}`);
        break;
      }
    }
    out.push({ key: step, text: `${step.toLowerCase().replace(/_/g, " ")} ${parts.join(" ")}`.trim() });
  }
  return out;
}

// ---------------------------------------------------------------------------
// The document
// ---------------------------------------------------------------------------

export function RunArtifactDocument({ artifact }: { artifact: ScannerRunArtifact }) {
  const { narrative, chart, matches, step_counters: counters } = artifact;
  const generatedLabel = useMemo(() => {
    const at = new Date(artifact.generated_at);
    return Number.isNaN(at.getTime()) ? "" : at.toISOString().replace("T", " ").slice(0, 16);
  }, [artifact.generated_at]);

  return (
    <section
      data-testid="scanner-run-artifact"
      data-fired={artifact.fired ? "true" : "false"}
      aria-label="Run result document"
      className="t-rise min-w-0 rounded-xl border border-border bg-surface p-4"
    >
      {/* Eyebrow + headline + fired pill */}
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
        {artifact.run_meta.scanner_name || "Scanner"} · run result
        {artifact.run_meta.is_test ? " · test run" : ""}
      </div>
      <div className="mt-1.5 flex flex-wrap items-start justify-between gap-3">
        <h2
          data-testid="artifact-headline"
          className="min-w-0 flex-1 text-xl font-black tracking-tight text-text sm:text-2xl"
        >
          {artifact.headline}
        </h2>
        <FiredPill fired={artifact.fired} />
      </div>
      <p className="mt-1 font-mono text-[11px] text-muted-2">
        {generatedLabel ? `generated ${generatedLabel} UTC` : "generated"} ·{" "}
        {counters.length} step{counters.length === 1 ? "" : "s"} · {matches.length} match
        {matches.length === 1 ? "" : "es"} ·{" "}
        {artifact.run_meta.duration_ms === null
          ? "—"
          : `${(artifact.run_meta.duration_ms / 1000).toFixed(1)}s`}{" "}
        · paper research only
      </p>

      {/* KPI tiles */}
      <div
        data-testid="artifact-kpis"
        className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
      >
        {artifact.kpis.map((kpi) => (
          <KpiTile key={kpi.label} label={kpi.label} value={kpi.value} delta={kpi.delta} />
        ))}
      </div>

      {/* Per-step funnel counters */}
      {counters.length > 0 ? (
        <div className="mt-4">
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            Step counters
          </h3>
          <ol
            data-testid="artifact-step-counters"
            className="mt-1.5 flex flex-wrap gap-2 font-mono text-[10.5px] font-bold"
          >
            {counters.map((counter) => (
              <li
                key={`${counter.index}-${counter.step}`}
                title={
                  counter.measured
                    ? `${counter.step}: ${counter.in} in, ${counter.out} out`
                    : `${counter.step}: funnel point not recorded for this run`
                }
                className={cn(
                  "rounded border px-2 py-1",
                  counter.measured
                    ? "border-border bg-bg/60 text-muted"
                    : "border-dashed border-border bg-bg/40 text-muted-2",
                )}
              >
                <span className="text-text">{counter.step.toLowerCase().replace(/_/g, " ")}</span>{" "}
                <span className="tabular-nums">
                  {counter.in} → {counter.out}
                </span>
                {counter.measured ? null : <span className="ml-1">(not measured)</span>}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {/* Matched markets table */}
      <div className="mt-4">
        <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
          Matched markets
        </h3>
        {matches.length === 0 ? (
          <p data-testid="artifact-no-matches" className="mt-1.5 text-[13px] text-muted">
            {chart.empty_reason ?? "No market cleared every step."}
          </p>
        ) : (
          <div className="mt-1.5 -mx-1 overflow-x-auto px-1">
            <table
              data-testid="artifact-matches-table"
              className="w-full min-w-[560px] border-collapse text-left text-[12.5px]"
            >
              <thead>
                <tr className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
                  <th scope="col" className="py-1.5 pr-3 font-bold">
                    Market
                  </th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-bold">
                    Price
                  </th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-bold">
                    Volume
                  </th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-bold">
                    Locks
                  </th>
                  <th scope="col" className="py-1.5 text-right font-bold">
                    Signal
                  </th>
                </tr>
              </thead>
              <tbody>
                {matches.map((match) => (
                  <tr key={match.market_slug} className="border-t border-border/70 align-top">
                    <td className="py-2 pr-3">
                      <a
                        href={`/markets/${encodeURIComponent(match.market_slug)}`}
                        className="font-semibold text-text transition hover:text-primary"
                      >
                        {match.title}
                      </a>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {scoreChips(match).map((chip) => (
                          <span
                            key={chip.key}
                            className="rounded border border-border bg-bg/60 px-1.5 py-0.5 font-mono text-[10px] text-muted"
                          >
                            {chip.text}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums text-muted">
                      {priceLabel(match.price)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums text-muted">
                      {volumeLabel(match.volume)}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums text-muted">
                      {lockLabel(match.lock_at)}
                    </td>
                    <td className="py-2 text-right font-mono tabular-nums text-primary">
                      {match.score.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Chart */}
      {chart.series.length > 0 ? (
        <div className="mt-4">
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            {chart.title}
          </h3>
          <p className="mt-0.5 mb-1.5 text-[11.5px] text-muted-2">{chart.value_label}</p>
          <ArtifactBarChart series={chart.series} valueLabel={chart.value_label} />
        </div>
      ) : null}

      {/* Narrative — real DOM text, research actions only. */}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div data-testid="artifact-what-this-means">
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            What this means
          </h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            {narrative.what_this_means}
          </p>
        </div>
        <div data-testid="artifact-what-to-do-now">
          <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            What to do now
          </h3>
          <ul className="mt-1.5 space-y-1.5">
            {narrative.what_to_do_now.map((action) => (
              <li key={action} className="flex gap-2 text-[13px] leading-relaxed text-muted">
                <span aria-hidden className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-primary" />
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p
        data-testid="artifact-provenance"
        className="mt-4 rounded-lg border border-border bg-bg/50 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2"
      >
        narrative: {narrative.generator}
        {narrative.filtered ? " · trade language filtered" : ""} · numbers computed from
        the run · research only, never an instruction to trade
      </p>
    </section>
  );
}

/**
 * Fetches the artifact for a run and renders it. Renders nothing at all when
 * the backend has no artifact — an absent document is honest; a fabricated one
 * would not be.
 */
export function RunArtifact({
  scannerId,
  runId,
  token,
  className,
}: {
  scannerId: string;
  runId: string | null;
  token?: string | null;
  className?: string;
}) {
  const [artifact, setArtifact] = useState<ScannerRunArtifact | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!runId) {
      setArtifact(null);
      return () => {
        cancelled = true;
      };
    }
    void (async () => {
      const { artifact: next } = await getRunArtifact(scannerId, runId, token ?? null);
      if (!cancelled) setArtifact(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [scannerId, runId, token]);

  if (!artifact) return null;
  return (
    <div className={className}>
      <RunArtifactDocument artifact={artifact} />
    </div>
  );
}
