"use client";

import { EmptyState } from "@/components/EmptyState";
import { Panel } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import {
  alphaRejectionLabel,
  type AlphaFactors,
} from "@/lib/alpha-api";

/*
 * Loop 99 AU2 — factor ledger for the /alpha research view.
 * VALID factors wear a mint badge; KILLED factors wear gray — never red
 * (a rejected research signal is not an error, and red is reserved for
 * trade direction). Negative scores draw blue (`secondary`), not red.
 */

function ScoreBar({ score, muted }: { score: number; muted: boolean }) {
  const half = Math.min(50, Math.abs(score) * 50);
  return (
    <span className="relative mt-1 block h-1.5 w-24 rounded-full bg-surface-3" aria-hidden>
      <span className="absolute left-1/2 top-[-1px] h-[calc(100%+2px)] w-px bg-border-light" />
      {score >= 0 ? (
        <span
          className={cn(
            "absolute left-1/2 top-0 h-full rounded-r-full transition-[width] duration-300 ease-swift",
            muted ? "bg-muted-2/40" : "bg-primary/80",
          )}
          style={{ width: `${half}%` }}
        />
      ) : (
        <span
          className={cn(
            "absolute right-1/2 top-0 h-full rounded-l-full transition-[width] duration-300 ease-swift",
            muted ? "bg-muted-2/40" : "bg-secondary/80",
          )}
          style={{ width: `${half}%` }}
        />
      )}
    </span>
  );
}

function ValidBadge({ valid }: { valid: boolean }) {
  return valid ? (
    <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em] text-primary">
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
      VALID
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em] text-muted-2">
      <span className="h-1.5 w-1.5 rounded-full bg-muted-2/60" />
      KILLED
    </span>
  );
}

export function FactorTable({
  factors,
  market,
}: {
  factors: AlphaFactors | null;
  market: string;
}) {
  const rows = factors?.factors ?? [];

  return (
    <Panel
      title={
        <span className="flex items-baseline gap-2">
          Factor scores
          <span className="font-mono text-[11px] font-semibold normal-case tracking-normal text-muted-2">
            {market}
          </span>
        </span>
      }
      action={
        <span className="flex items-center gap-3 text-[11px] font-semibold text-muted-2">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" /> valid
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-muted-2/60" /> killed
          </span>
        </span>
      }
      padded={false}
      className="overflow-hidden"
    >
      <div className="min-h-[340px]" data-testid="alpha-factor-table">
        {factors && rows.length === 0 ? (
          <div className="p-4" data-testid="alpha-empty-state">
            <EmptyState
              icon="proof"
              title="No factor runs yet"
              body="Factor scores appear once the model locks a forecast for this market and the seven research signals are captured. Nothing here is an error — the ledger is simply empty."
              cta={{
                href: `/markets/${encodeURIComponent(market)}`,
                label: "Open the market",
              }}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-[10px] font-black uppercase tracking-[0.12em] text-muted-2">
                  <th scope="col" className="px-4 py-2.5 sm:px-5">
                    Factor
                  </th>
                  <th scope="col" className="px-3 py-2.5">
                    Score
                  </th>
                  <th scope="col" className="px-3 py-2.5 text-right">
                    t-stat
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right sm:px-5">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((factor) => (
                  <tr
                    key={factor.name}
                    data-testid="alpha-factor-row"
                    data-valid={factor.valid}
                    className={cn(
                      "border-b border-border/60 transition-colors duration-150 hover:bg-surface-2/70",
                      !factor.valid && "opacity-80",
                    )}
                  >
                    <td className="px-4 py-3 sm:px-5">
                      <span className="font-mono text-[13px] font-bold text-text">
                        {factor.name}
                      </span>
                      {!factor.valid && factor.reason ? (
                        <span className="mt-0.5 block text-[11px] leading-snug text-muted-2">
                          {alphaRejectionLabel(factor.reason)}
                        </span>
                      ) : !factor.provenance.available && factor.provenance.reason ? (
                        <span className="mt-0.5 block text-[11px] leading-snug text-muted-2">
                          {alphaRejectionLabel(factor.provenance.reason)}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={cn(
                          "font-mono text-[13px] font-black tabular-nums",
                          !factor.valid
                            ? "text-muted-2"
                            : factor.score >= 0
                              ? "text-primary"
                              : "text-secondary",
                        )}
                      >
                        {factor.score >= 0 ? "+" : ""}
                        {factor.score.toFixed(2)}
                      </span>
                      <ScoreBar score={factor.score} muted={!factor.valid} />
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span
                        className={cn(
                          "font-mono text-[13px] font-semibold tabular-nums",
                          factor.t_stat === null
                            ? "text-muted-2"
                            : factor.valid
                              ? "text-text"
                              : "text-muted",
                        )}
                      >
                        {factor.t_stat === null ? "—" : factor.t_stat.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right sm:px-5">
                      <ValidBadge valid={factor.valid} />
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

export function FactorTableSkeleton() {
  return (
    <Panel title="Factor scores" padded={false}>
      <div className="min-h-[340px] space-y-3 p-4 sm:p-5" data-testid="alpha-skeleton">
        {Array.from({ length: 7 }, (_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="skeleton h-4 w-32" />
            <div className="skeleton h-4 w-20" />
            <div className="skeleton ml-auto h-4 w-12" />
            <div className="skeleton h-5 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </Panel>
  );
}
