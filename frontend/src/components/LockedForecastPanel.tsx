"use client";

/**
 * F2 (loop47): market-detail locked forecast panel.
 * Surfaces GET /api/v1/markets/{slug}/locked-forecast only — never fabricates %.
 */
import { useEffect, useState } from "react";
import {
  buildLockedForecastView,
  fetchLockedForecast,
  type LockedForecastResponse,
  type LockedForecastView,
} from "@/lib/locked-forecast-api";
import { cn } from "@/lib/cn";

const PROVISIONAL_DISCLAIMER =
  "PROVISIONAL — locked model forecast is not yet CLV-validated.";

export function LockedForecastPanel({ slug }: { slug: string }) {
  const [raw, setRaw] = useState<LockedForecastResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    setLoaded(false);
    void fetchLockedForecast(slug).then((r) => {
      if (dead) return;
      setRaw(r);
      setLoaded(true);
    });
    return () => {
      dead = true;
    };
  }, [slug]);

  const view = buildLockedForecastView(raw, { loading: !loaded });
  return <LockedForecastPanelBody view={view} />;
}

/** Pure presentational body — unit-testable without fetch. */
export function LockedForecastPanelBody({ view }: { view: LockedForecastView }) {
  if (view.state === "loading") {
    return (
      <div
        data-testid="locked-forecast-panel"
        className="rounded-2xl border border-border bg-surface p-4"
        aria-busy="true"
      >
        <div className="skeleton h-3 w-40 rounded" />
        <div className="skeleton mt-3 h-8 w-full rounded" />
      </div>
    );
  }

  if (view.state === "unavailable" || view.state === "pre_lock") {
    return (
      <div
        data-testid="locked-forecast-panel"
        className="rounded-2xl border border-dashed border-border bg-surface p-4"
      >
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-text">Model forecast</h3>
          <span className="rounded-pill bg-secondary-dim px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-accent">
            {view.state === "pre_lock" ? "Pre-lock" : "Unavailable"}
          </span>
        </div>
        <p className="mt-2 text-sm text-muted">{view.emptyCopy}</p>
        {view.currentProbLabel ? (
          <p className="mt-2 font-mono text-xs text-muted-2">
            Market now {view.currentProbLabel}
          </p>
        ) : null}
        {view.provisional ? (
          <p className="mt-3 text-[11px] font-medium text-gold">{PROVISIONAL_DISCLAIMER}</p>
        ) : null}
      </div>
    );
  }

  const deltaTone =
    view.deltaPts === null
      ? "text-muted"
      : view.deltaPts > 0
        ? "text-primary"
        : view.deltaPts < 0
          ? "text-danger"
          : "text-muted";

  return (
    <div
      data-testid="locked-forecast-panel"
      className="rounded-2xl border border-border bg-surface p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-text">Model forecast</h3>
        <span className="rounded-pill bg-secondary-dim px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-accent">
          Locked
        </span>
        {view.provisional ? (
          <span className="rounded-pill bg-gold/20 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-gold">
            Provisional
          </span>
        ) : null}
      </div>

      <p className="mt-2 text-sm leading-relaxed text-text">
        Model: locked{" "}
        <span className="font-mono font-bold text-accent">{view.lockedProbLabel}</span>
        {view.lockedAtRelative ? (
          <>
            {" "}
            on <span className="font-mono text-muted">{view.lockedAtRelative}</span>
          </>
        ) : null}
        {view.currentProbLabel ? (
          <>
            {" "}
            · market now{" "}
            <span className="font-mono font-bold text-text">{view.currentProbLabel}</span>
          </>
        ) : null}
      </p>

      {view.deltaLabel ? (
        <p className={cn("mt-2 font-mono text-sm font-semibold tabular-nums", deltaTone)}>
          {view.deltaLabel}
        </p>
      ) : null}

      {view.provisional ? (
        <p className="mt-3 border-t border-border pt-3 text-[11px] font-medium text-gold">
          {PROVISIONAL_DISCLAIMER}
        </p>
      ) : null}
    </div>
  );
}
