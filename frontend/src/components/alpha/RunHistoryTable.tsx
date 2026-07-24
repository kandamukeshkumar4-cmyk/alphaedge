"use client";

import { EmptyState } from "@/components/EmptyState";
import { Panel } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import {
  alphaRunStatusLabel,
  type AlphaRuns,
} from "@/lib/alpha-runs-api";

/*
 * Loop 102 AR2 — Run-history ledger for the /alpha research view.
 *
 * One row per daily alpha research run: date, validator status, residual
 * alpha, Newey-West t-stat, and whether a signal was emitted. Signal YES
 * wears a mint badge; NO wears gray — never red (a withheld signal is the
 * validator working, and red is reserved for trade direction).
 */

function formatRunDate(value: string): string {
  if (!value) return "—";
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) return value;
  return new Date(ms).toISOString().slice(0, 10);
}

function formatResidual(value: number | null): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
}

function SignalBadge({ emitted }: { emitted: boolean }) {
  return emitted ? (
    <span
      data-signal="yes"
      className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em] text-primary"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
      YES
    </span>
  ) : (
    <span
      data-signal="no"
      className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em] text-muted-2"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-muted-2/60" />
      NO
    </span>
  );
}

export function RunHistoryTable({ runs }: { runs: AlphaRuns | null }) {
  const rows = runs?.items ?? [];

  return (
    <Panel
      title="Run history"
      action={
        <span className="flex items-center gap-3 text-[11px] font-semibold text-muted-2">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" /> signal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-muted-2/60" /> withheld
          </span>
        </span>
      }
      padded={false}
      className="overflow-hidden"
    >
      <div className="min-h-[280px]" data-testid="alpha-run-history">
        {runs && rows.length === 0 ? (
          <div className="p-4" data-testid="alpha-runs-empty-state">
            <EmptyState
              icon="signal"
              title="No research runs yet"
              body="The alpha research tail runs daily. Each run validates the factor graph out-of-sample and records whether the residual alpha beat the closing line. Nothing here is an error — the ledger is simply empty."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-[10px] font-black uppercase tracking-[0.12em] text-muted-2">
                  <th scope="col" className="px-4 py-2.5 sm:px-5">
                    Date
                  </th>
                  <th scope="col" className="px-3 py-2.5">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-2.5 text-right">
                    Residual α
                  </th>
                  <th scope="col" className="px-3 py-2.5 text-right">
                    t-stat
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right sm:px-5">
                    Signal
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((run) => (
                  <tr
                    key={run.id}
                    data-testid="alpha-run-row"
                    data-emitted={String(run.signal_emitted)}
                    className="border-b border-border/60 transition-colors duration-150 hover:bg-surface-2/70"
                  >
                    <td className="px-4 py-3 sm:px-5">
                      <span className="font-mono text-[13px] font-bold tabular-nums text-text">
                        {formatRunDate(run.started_at)}
                      </span>
                      {!run.finished_at ? (
                        <span className="mt-0.5 block text-[11px] leading-snug text-muted-2">
                          in flight
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={cn(
                          "text-[12px] font-semibold",
                          run.signal_emitted ? "text-text" : "text-muted",
                        )}
                      >
                        {alphaRunStatusLabel(run.status)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span
                        className={cn(
                          "font-mono text-[13px] font-black tabular-nums",
                          run.residual_alpha === null
                            ? "text-muted-2"
                            : run.signal_emitted
                              ? "text-primary"
                              : "text-text",
                        )}
                      >
                        {formatResidual(run.residual_alpha)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span
                        className={cn(
                          "font-mono text-[13px] font-semibold tabular-nums",
                          run.t_stat === null
                            ? "text-muted-2"
                            : run.signal_emitted
                              ? "text-text"
                              : "text-muted",
                        )}
                      >
                        {run.t_stat === null ? "—" : run.t_stat.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right sm:px-5">
                      <SignalBadge emitted={run.signal_emitted} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

export function RunHistoryTableSkeleton() {
  return (
    <Panel title="Run history" padded={false}>
      <div className="min-h-[280px] space-y-3 p-4 sm:p-5" data-testid="alpha-runs-skeleton">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-4 w-32" />
            <div className="skeleton ml-auto h-4 w-16" />
            <div className="skeleton h-4 w-12" />
            <div className="skeleton h-5 w-14 rounded-full" />
          </div>
        ))}
      </div>
    </Panel>
  );
}
