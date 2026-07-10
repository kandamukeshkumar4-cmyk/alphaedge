"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  buildModelAbView,
  fetchModelAb,
  fetchResolvedCount,
  type ModelAbResponse,
  type ResolvedCountResponse,
} from "@/lib/model-ab-api";

/**
 * W03 — LightGBM-vs-XGBoost A/B readout card. Progress bar toward the resolve
 * threshold, then the Brier comparison once ready — always with an explicit
 * "default unchanged — analysis only" note. Honest not-ready + lgbm-unavailable
 * states. Fetch-once on mount (no poll loop).
 */
export function ModelAbCard() {
  const [ab, setAb] = useState<ModelAbResponse | null>(null);
  const [resolved, setResolved] = useState<ResolvedCountResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    void Promise.all([fetchModelAb(), fetchResolvedCount()]).then(([a, r]) => {
      if (dead) return;
      setAb(a);
      setResolved(r);
      setLoaded(true);
    });
    return () => {
      dead = true;
    };
  }, []);

  const view = buildModelAbView(ab, resolved);
  const state = loaded ? view.state : "loading";

  return (
    <section data-testid="model-ab-card" className="mt-10">
      <h2 className="text-lg font-black text-text">
        LightGBM vs XGBoost (walk-forward A/B)
      </h2>
      <p className="mt-1 text-sm text-muted">
        Runs the resolved-market harness once enough outcomes exist. This is{" "}
        <span className="font-bold text-primary">analysis only</span> — the deployed
        default model never changes automatically.
      </p>

      {state === "loading" ? (
        <div className="mt-4 rounded-2xl border border-border bg-surface p-4">
          <div className="skeleton h-3 w-40 rounded" />
          <div className="skeleton mt-3 h-2.5 w-full rounded-full" />
          <div className="skeleton mt-4 h-10 w-full rounded" />
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-border bg-surface p-4">
          {/* Progress toward the threshold — shown in every state. */}
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold uppercase tracking-[0.06em] text-muted">
              Resolved outcomes
            </span>
            <span className="font-mono font-bold text-text">{view.resolvedLabel}</span>
          </div>
          <div
            className="mt-2 h-2.5 overflow-hidden rounded-full bg-surface-3"
            role="progressbar"
            aria-valuenow={Math.round(view.progressPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`A/B unblock progress: ${view.resolvedLabel}`}
          >
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{ width: `${view.progressPct}%` }}
            />
          </div>

          {state === "not-ready" ? (
            <p className="mt-3 text-xs text-muted">
              {view.remaining} more resolved outcome{view.remaining === 1 ? "" : "s"} needed before
              the walk-forward A/B can run. Default model:{" "}
              <span className="font-mono font-semibold text-text">{view.defaultModelLabel}</span>{" "}
              (unchanged).
            </p>
          ) : (
            <>
              <dl className="mt-4 grid grid-cols-2 gap-3">
                <BrierStat label="XGBoost Brier" value={view.xgbBrierLabel} />
                <BrierStat
                  label="LightGBM Brier"
                  value={view.lgbmBrierLabel}
                  muted={state === "lgbm-unavailable"}
                />
                {view.deltaLabel ? (
                  <BrierStat label="Δ (XGB − LGBM)" value={view.deltaLabel} />
                ) : null}
                {view.winnerLabel ? (
                  <BrierStat label="Would win (lower Brier)" value={view.winnerLabel} />
                ) : null}
              </dl>

              {view.unavailableNote ? (
                <p className="mt-3 rounded-lg border border-gold/30 bg-gold/10 px-3 py-2 text-xs text-gold">
                  {view.unavailableNote}
                </p>
              ) : null}

              <p className="mt-3 rounded-lg border border-primary/25 bg-primary-dim/40 px-3 py-2 text-xs font-semibold text-primary">
                Default unchanged — analysis only. The A/B never flips the deployed model
                ({view.defaultModelLabel}); it reports which would have scored better on real
                resolutions.
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function BrierStat({
  label,
  value,
  muted,
}: {
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg/40 p-3">
      <dt className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted">{label}</dt>
      <dd className={cn("mt-1 font-mono text-lg font-bold", muted ? "text-muted-2" : "text-text")}>
        {value}
      </dd>
    </div>
  );
}
