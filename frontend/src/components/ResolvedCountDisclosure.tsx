"use client";

/**
 * F3 (loop47): honest readout of GET /api/v1/system/resolved-count disclosure
 * fields — ``forecast_scored_count`` + ``source``. Never fabricates either value.
 */
import { useEffect, useState } from "react";
import {
  buildResolvedCountDisclosure,
  fetchResolvedCount,
  type ResolvedCountDisclosure as DisclosureView,
  type ResolvedCountResponse,
} from "@/lib/model-ab-api";
import { cn } from "@/lib/cn";

export function ResolvedCountDisclosure() {
  const [raw, setRaw] = useState<ResolvedCountResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    void fetchResolvedCount().then((r) => {
      if (dead) return;
      setRaw(r);
      setLoaded(true);
    });
    return () => {
      dead = true;
    };
  }, []);

  const view = buildResolvedCountDisclosure(raw);

  if (!loaded) {
    return (
      <div
        data-testid="resolved-count-disclosure"
        className="rounded-2xl border border-border bg-surface p-4"
        aria-busy="true"
      >
        <div className="skeleton h-3 w-48 rounded" />
        <div className="skeleton mt-3 h-8 w-full rounded" />
      </div>
    );
  }

  if (!view) {
    return (
      <div
        data-testid="resolved-count-disclosure"
        className="rounded-2xl border border-dashed border-border bg-surface p-4 text-sm text-muted"
      >
        Resolved-count readout unavailable — API not reachable. Nothing fabricated.
      </div>
    );
  }

  return <ResolvedCountDisclosureBody view={view} />;
}

function ResolvedCountDisclosureBody({ view }: { view: DisclosureView }) {
  return (
    <div
      data-testid="resolved-count-disclosure"
      className={cn(
        "rounded-2xl border p-4 sm:p-5",
        view.isPaperOrdersFallback
          ? "border-gold/40 bg-gold/10"
          : "border-border bg-surface",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-text">Resolved-count population</h3>
        <span
          className={cn(
            "rounded-pill px-2 py-0.5 font-mono text-[10px] font-semibold uppercase",
            view.isPaperOrdersFallback
              ? "bg-gold/20 text-gold"
              : "bg-secondary-dim text-accent",
          )}
        >
          {view.sourceLabel}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-muted">{view.sourceDetail}</p>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        <Stat
          label="resolved_count"
          value={String(view.resolvedCount)}
          hint="Gate progress numerator"
        />
        <Stat
          label="forecast_scored_count"
          value={
            view.forecastScoredCount === null ? "—" : String(view.forecastScoredCount)
          }
          hint="Scored LIVE ForecastLog rows only"
          muted={view.forecastScoredCount === null}
        />
      </dl>

      {view.source ? (
        <p className="mt-3 font-mono text-[11px] text-muted-2">
          source=<span className="text-text">{view.source}</span>
        </p>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
  muted,
}: {
  label: string;
  value: string;
  hint: string;
  muted?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg/40 px-3 py-2.5">
      <dt className="font-mono text-[10px] font-bold uppercase tracking-[0.06em] text-muted">
        {label}
      </dt>
      <dd
        className={cn(
          "mt-1 font-mono text-xl font-bold",
          muted ? "text-muted-2" : "text-text",
        )}
      >
        {value}
      </dd>
      <p className="mt-0.5 text-[11px] text-muted-2">{hint}</p>
    </div>
  );
}
