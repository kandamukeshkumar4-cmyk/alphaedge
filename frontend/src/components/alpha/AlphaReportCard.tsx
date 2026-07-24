"use client";

import { Panel } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import {
  alphaRejectionLabel,
  type AlphaReport,
} from "@/lib/alpha-api";

/*
 * Loop 99 AU2 — validated-factor summary card (GET /api/v1/alpha/report).
 * Shows which factors beat the closing line out-of-sample (OOS Brier vs
 * closing Brier) and why the rest were killed. Killed factors are gray —
 * rejection is research hygiene, never an alarm.
 */

function brier(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}

export function AlphaReportCard({ report }: { report: AlphaReport | null }) {
  const factors = report?.factors ?? [];
  const valid = factors.filter((f) => f.valid);
  const killed = factors.filter((f) => !f.valid);
  const total = factors.length;

  return (
    <Panel
      title="Validated factors"
      action={
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em]",
            total > 0 && valid.length > 0
              ? "border-primary/40 bg-primary/10 text-primary"
              : "border-border bg-surface-2 text-muted-2",
          )}
        >
          {report ? `${valid.length}/${total} SURVIVE` : "…"}
        </span>
      }
      className="lg:sticky lg:top-24"
    >
      <div data-testid="alpha-report-card" className="min-h-[280px]">
        <p className="text-[12px] leading-relaxed text-muted">
          A factor is shown as an edge only if it{" "}
          <span className="font-semibold text-text">beats the closing line out-of-sample</span>{" "}
          with a positive block-bootstrap CI and a Newey-West t above threshold.
          Everything else is killed — paper-only research, no order path.
        </p>

        {report && factors.length === 0 ? (
          <p
            className="mt-4 rounded-xl border border-border bg-surface-2/60 px-3 py-3 text-[12px] text-muted-2"
            data-testid="alpha-report-empty"
          >
            No validation runs yet. The validator reports here once locked
            forecasts with closing lines exist on the backend.
          </p>
        ) : (
          <>
            <div className="mt-4 space-y-2">
              {(report ? valid : []).map((f) => {
                const improvement =
                  f.closing_brier !== null && f.oos_brier !== null
                    ? f.closing_brier - f.oos_brier
                    : null;
                return (
                  <div
                    key={f.name}
                    data-testid="alpha-report-valid-row"
                    className="rounded-xl border border-primary/25 bg-primary-dim/30 px-3 py-2.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[12px] font-black text-text">
                        {f.name}
                      </span>
                      {improvement !== null && improvement > 0 ? (
                        <span className="font-mono text-[11px] font-black tabular-nums text-primary">
                          ▲ {improvement.toFixed(3)} vs close
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-1.5 grid grid-cols-3 gap-2 font-mono text-[11px] tabular-nums">
                      <span className="text-muted-2">
                        oos{" "}
                        <span className="font-bold text-muted">{brier(f.oos_brier)}</span>
                      </span>
                      <span className="text-muted-2">
                        close{" "}
                        <span className="font-bold text-muted">{brier(f.closing_brier)}</span>
                      </span>
                      <span className="text-muted-2">
                        t{" "}
                        <span className="font-bold text-muted">
                          {f.t_stat === null ? "—" : f.t_stat.toFixed(2)}
                        </span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {killed.length > 0 ? (
              <div className="mt-4">
                <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-2">
                  Killed by the validator
                </p>
                <ul className="mt-2 space-y-1.5">
                  {killed.map((f) => (
                    <li
                      key={f.name}
                      data-testid="alpha-report-killed-row"
                      className="flex items-baseline justify-between gap-3 text-[12px]"
                    >
                      <span className="shrink-0 font-mono font-bold text-muted-2">
                        {f.name}
                      </span>
                      <span className="text-right leading-snug text-muted-2">
                        {alphaRejectionLabel(f.reason)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </div>
    </Panel>
  );
}

export function AlphaReportCardSkeleton() {
  return (
    <Panel title="Validated factors">
      <div className="min-h-[280px] space-y-3" data-testid="alpha-report-skeleton">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-3/4" />
        <div className="skeleton h-14 w-full rounded-xl" />
        <div className="skeleton h-14 w-full rounded-xl" />
        <div className="skeleton h-3 w-1/2" />
        <div className="skeleton h-3 w-2/3" />
      </div>
    </Panel>
  );
}
