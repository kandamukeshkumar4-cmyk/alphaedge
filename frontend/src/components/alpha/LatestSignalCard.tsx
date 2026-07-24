"use client";

import { cn } from "@/lib/cn";
import type { LatestSignal } from "@/lib/alpha-runs-api";

/*
 * Loop 102 AR2 — Latest-signal hero card for the /alpha research view.
 *
 * Emitted signal → MINT ("Edge found, t-stat X.X"). Withheld signal → GRAY
 * ("No signal today — evidence: …"), NEVER red: a withheld signal is the
 * validator doing its job, not an error, and red is reserved for trade
 * direction. Paper research only — a signal appears only when the residual
 * alpha beats the closing line out-of-sample.
 */

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) return value;
  return new Date(ms).toISOString().slice(0, 16).replace("T", " ");
}

function formatResidual(value: number | null): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
}

function formatTStat(value: number | null): string {
  return value === null ? "—" : value.toFixed(1);
}

export function LatestSignalCard({ signal }: { signal: LatestSignal }) {
  const { emitted } = signal;
  const weightEntries = Object.entries(signal.weights ?? {});

  return (
    <section
      data-testid="alpha-latest-signal"
      data-emitted={String(emitted)}
      aria-label="Latest alpha signal"
      className={cn(
        "relative min-h-[168px] overflow-hidden rounded-2xl border p-5 sm:p-6",
        emitted
          ? "border-primary/40 bg-primary-dim/40"
          : "border-border bg-surface-2/70",
      )}
    >
      <p
        className={cn(
          "font-mono text-[10px] font-black uppercase tracking-[0.14em]",
          emitted ? "text-primary" : "text-muted-2",
        )}
      >
        {emitted ? "Latest signal · OOS validated" : "Latest signal · withheld"}
      </p>

      <h2
        data-testid="alpha-latest-signal-headline"
        className={cn(
          "mt-2 text-xl font-black leading-tight tracking-tight sm:text-2xl",
          emitted ? "text-primary" : "text-text",
        )}
      >
        {emitted
          ? `Edge found, t-stat ${formatTStat(signal.t_stat)}`
          : "No signal today"}
      </h2>

      <p
        data-testid="alpha-latest-signal-evidence"
        className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-muted"
      >
        {emitted
          ? signal.evidence.trim() !== ""
            ? signal.evidence
            : "The combined research portfolio beat the closing line out-of-sample."
          : `evidence: ${
              signal.evidence.trim() !== ""
                ? signal.evidence
                : "No run has beaten the closing line out-of-sample yet."
            }`}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2">
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            Residual α
          </span>
          <span
            className={cn(
              "font-mono text-[13px] font-black tabular-nums",
              emitted ? "text-primary" : "text-text",
            )}
          >
            {formatResidual(signal.residual_alpha)}
          </span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            t-stat
          </span>
          <span
            className={cn(
              "font-mono text-[13px] font-black tabular-nums",
              emitted ? "text-primary" : "text-text",
            )}
          >
            {signal.t_stat === null ? "—" : signal.t_stat.toFixed(2)}
          </span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
            As of
          </span>
          <span className="font-mono text-[12px] font-semibold tabular-nums text-muted">
            {formatTimestamp(signal.created_at)} UTC
          </span>
        </span>
      </div>

      {emitted && weightEntries.length > 0 ? (
        <div
          data-testid="alpha-latest-signal-weights"
          className="mt-3 flex flex-wrap gap-1.5"
        >
          {weightEntries.map(([factor, weight]) => (
            <span
              key={factor}
              className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold tracking-[0.06em] text-primary"
            >
              {factor}
              <span className="tabular-nums text-primary/80">
                {(weight * 100).toFixed(0)}%
              </span>
            </span>
          ))}
        </div>
      ) : null}

      <p className="mt-4 font-mono text-[10px] leading-relaxed text-muted-2">
        paper research · a signal shows only if the residual alpha beats the
        closing line out-of-sample · simulated funds only
      </p>
    </section>
  );
}

export function LatestSignalCardSkeleton() {
  return (
    <section
      aria-label="Latest alpha signal"
      className="min-h-[168px] rounded-2xl border border-border bg-surface-2/70 p-5 sm:p-6"
    >
      <div data-testid="alpha-signal-skeleton" className="space-y-3">
        <div className="skeleton h-3 w-44" />
        <div className="skeleton h-7 w-72 max-w-full" />
        <div className="skeleton h-4 w-full max-w-xl" />
        <div className="flex gap-6 pt-1">
          <div className="skeleton h-4 w-24" />
          <div className="skeleton h-4 w-20" />
          <div className="skeleton h-4 w-36" />
        </div>
      </div>
    </section>
  );
}
