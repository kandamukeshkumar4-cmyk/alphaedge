"use client";

import Link from "next/link";

import { ScannerStatusPill } from "@/components/scanners/ScannerStatusPill";
import { cn } from "@/lib/cn";
import {
  relativeTimeLabel,
  runDurationLabel,
  scheduleLabel,
  type Scanner,
  type ScannerStepType,
} from "@/lib/scanners-api";

/*
 * Loop V84 (U2) — one scanner in the studio grid: name, status pill,
 * "every N min" schedule line, last-run time, run-now + pause/resume.
 * Entrance stagger via the terminal motion classes (t-rise/t-stagger-*),
 * which the globals.css reduced-motion kill-switch already zeroes.
 */

const STEP_ABBREV: Record<ScannerStepType, string> = {
  WHALE_FLOW: "flow",
  PRICE_TREND: "trend",
  NEWS_SENTIMENT: "news",
  MODEL_EDGE: "model",
  DIRECTION_ALIGNMENT: "align",
};

function staggerClass(index: number): string {
  const capped = Math.min(Math.max(index, 0), 4);
  return capped === 0 ? "" : `t-stagger-${capped}`;
}

export function ScannerCard({
  scanner,
  index,
  running,
  onRun,
  onPause,
  onResume,
}: {
  scanner: Scanner;
  index: number;
  running: boolean;
  onRun: (id: string) => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
}) {
  const paused = scanner.status === "paused";
  const lastRun = scanner.latest_run;
  const categories = scanner.spec.universe.categories;

  return (
    <article
      data-testid="scanner-card"
      className={cn(
        "t-rise group relative flex flex-col rounded-xl border border-border bg-surface p-4 shadow-card transition duration-200 ease-swift",
        "hover:-translate-y-0.5 hover:border-primary/45 hover:shadow-glow",
        "motion-reduce:transform-none motion-reduce:transition-none",
        staggerClass(index),
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/scanners/${scanner.id}`}
          className="min-w-0 flex-1 truncate text-[15px] font-black tracking-tight text-text transition group-hover:text-primary"
          title={scanner.name}
        >
          {scanner.name}
        </Link>
        <ScannerStatusPill status={scanner.status} />
      </div>

      <p className="mt-1.5 line-clamp-2 min-h-[34px] text-[12.5px] leading-snug text-muted">
        {scanner.description ?? "No description — compiled from a plain-English request."}
      </p>

      {/* Pipeline preview — one mono chip per spec step, in order. */}
      <div className="mt-2.5 flex flex-wrap gap-1" aria-label="Spec steps">
        {scanner.spec.steps.map((step, i) => (
          <span
            key={`${step.type}-${i}`}
            className="rounded border border-border bg-bg/60 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.1em] text-muted-2"
          >
            {STEP_ABBREV[step.type]}
          </span>
        ))}
      </div>

      <dl className="mt-3 space-y-1 font-mono text-[11px] text-muted">
        <div className="flex items-center gap-1.5">
          <dt className="text-muted-2">schedule</dt>
          <dd className="font-bold text-text">
            {scheduleLabel(scanner.spec)}
            <span className="font-normal text-muted-2"> · {scanner.spec.schedule.timezone}</span>
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt className="text-muted-2">universe</dt>
          <dd className="font-bold text-text">
            {categories.length > 0 ? categories.join(" · ") : "all markets"}
            {scanner.spec.universe.minimum_volume > 0
              ? ` · vol ≥ ${(scanner.spec.universe.minimum_volume / 1000).toFixed(0)}k`
              : ""}
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt className="text-muted-2">last run</dt>
          <dd className="font-bold text-text">
            {running ? (
              <span className="inline-flex items-center gap-1.5 text-secondary">
                <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" />
                running…
              </span>
            ) : lastRun ? (
              <>
                {relativeTimeLabel(lastRun.started_at)}
                <span className="font-normal text-muted-2">
                  {" "}
                  · {lastRun.status} · {runDurationLabel(lastRun)}
                </span>
              </>
            ) : (
              <span className="font-normal text-muted-2">never</span>
            )}
          </dd>
        </div>
      </dl>

      <div className="mt-auto flex items-center gap-2 border-t border-border/60 pt-3">
        <button
          type="button"
          disabled={running || paused}
          onClick={() => onRun(scanner.id)}
          title={paused ? "Resume the scanner to run it" : "Run this scanner now (paper)"}
          className={cn(
            "inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary/15 px-3 font-mono text-[11px] font-black uppercase tracking-[0.1em] text-primary transition",
            "hover:bg-primary hover:text-bg active:scale-95",
            "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
          )}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M6 4.5v15l13-7.5-13-7.5z" />
          </svg>
          {running ? "Running" : "Run now"}
        </button>
        <button
          type="button"
          disabled={running || scanner.status === "draft"}
          onClick={() => (paused ? onResume(scanner.id) : onPause(scanner.id))}
          title={scanner.status === "draft" ? "Run the scanner once before pausing" : undefined}
          className={cn(
            "inline-flex h-8 items-center rounded-lg border border-border px-3 font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-muted transition",
            "hover:border-border-light hover:text-text active:scale-95",
            "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
          )}
        >
          {paused ? "Resume" : "Pause"}
        </button>
        <Link
          href={`/scanners/${scanner.id}`}
          className="ml-auto inline-flex h-8 items-center rounded-lg px-2 font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-muted-2 transition hover:text-primary"
        >
          Open →
        </Link>
      </div>
    </article>
  );
}
