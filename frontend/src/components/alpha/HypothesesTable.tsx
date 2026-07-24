"use client";

import { EmptyState } from "@/components/EmptyState";
import { Panel } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import type { Hypotheses } from "@/lib/alpha-runs-api";

/*
 * Loop 102 AR3 — idea-generator proposals for the /alpha research view.
 *
 * VALIDATED proposals wear a mint badge; REJECTED proposals wear gray with
 * the validator's reason — never red (a rejected idea is research evidence,
 * not an error, and red is reserved for trade direction). Skeletons carry
 * reserved heights (no CLS) and honor prefers-reduced-motion via the global
 * `.skeleton` rule.
 */

function ValidatedBadge({ validated }: { validated: boolean }) {
  return validated ? (
    <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em] text-primary">
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
      VALIDATED
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em] text-muted-2">
      <span className="h-1.5 w-1.5 rounded-full bg-muted-2/60" />
      REJECTED
    </span>
  );
}

function DirectionChip({ direction }: { direction: string | null }) {
  if (!direction) {
    return <span className="font-mono text-[11px] text-muted-2">—</span>;
  }
  return (
    <span className="inline-flex items-center rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted">
      {direction}
    </span>
  );
}

export function HypothesesTable({ hypotheses }: { hypotheses: Hypotheses | null }) {
  const rows = hypotheses?.items ?? [];

  return (
    <Panel
      title="Proposed hypotheses"
      action={
        <span className="flex items-center gap-3 text-[11px] font-semibold text-muted-2">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" /> validated
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-muted-2/60" /> rejected
          </span>
        </span>
      }
      padded={false}
      className="overflow-hidden"
    >
      <div className="min-h-[280px]" data-testid="alpha-hypotheses">
        {hypotheses && rows.length === 0 ? (
          <div className="p-4" data-testid="alpha-hypotheses-empty-state">
            <EmptyState
              icon="radar"
              title="No hypotheses proposed yet"
              body="The idea generator proposes research hypotheses from the factor graph, and the validator judges each one out-of-sample. Nothing here is an error — there is simply nothing on the board yet."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-[10px] font-black uppercase tracking-[0.12em] text-muted-2">
                  <th scope="col" className="px-4 py-2.5 sm:px-5">
                    Hypothesis
                  </th>
                  <th scope="col" className="px-3 py-2.5">
                    Direction
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right sm:px-5">
                    Verdict
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((hypothesis) => (
                  <tr
                    key={hypothesis.name}
                    data-testid="alpha-hypothesis-row"
                    data-validated={String(hypothesis.validated)}
                    className={cn(
                      "border-b border-border/60 transition-colors duration-150 hover:bg-surface-2/70",
                      !hypothesis.validated && "opacity-80",
                    )}
                  >
                    <td className="px-4 py-3 sm:px-5">
                      <span className="font-mono text-[13px] font-bold text-text">
                        {hypothesis.name}
                      </span>
                      {hypothesis.description ? (
                        <span className="mt-0.5 block max-w-xl text-[11px] leading-snug text-muted-2">
                          {hypothesis.description}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <DirectionChip direction={hypothesis.predicted_direction} />
                    </td>
                    <td className="px-4 py-3 text-right sm:px-5">
                      <ValidatedBadge validated={hypothesis.validated} />
                      {!hypothesis.validated && hypothesis.reason ? (
                        <span className="mt-1 block text-[11px] leading-snug text-muted-2">
                          {hypothesis.reason}
                        </span>
                      ) : null}
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

export function HypothesesTableSkeleton() {
  return (
    <Panel title="Proposed hypotheses" padded={false}>
      <div
        className="min-h-[280px] space-y-3 p-4 sm:p-5"
        data-testid="alpha-hypotheses-skeleton"
      >
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="space-y-1.5">
              <div className="skeleton h-4 w-40" />
              <div className="skeleton h-3 w-64 max-w-full" />
            </div>
            <div className="skeleton ml-auto h-4 w-12" />
            <div className="skeleton h-5 w-20 rounded-full" />
          </div>
        ))}
      </div>
    </Panel>
  );
}
