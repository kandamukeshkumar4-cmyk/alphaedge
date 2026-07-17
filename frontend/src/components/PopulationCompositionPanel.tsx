"use client";

import { useEffect, useState } from "react";
import { MotionReveal } from "@/components/MotionReveal";
import { cn } from "@/lib/cn";
import {
  fetchResolvedCount,
  type PopulationHistogramEntry,
  type ResolvedCountPopulation,
  type ResolvedCountResponse,
} from "@/lib/model-ab-api";

/**
 * V53 read-only composition disclosure. Every displayed value comes directly
 * from the resolved-count population payload; no shares are regrouped client-side.
 */
export function PopulationCompositionPanel() {
  const [raw, setRaw] = useState<ResolvedCountResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    void fetchResolvedCount().then((response) => {
      if (dead) return;
      setRaw(response);
      setLoaded(true);
    });
    return () => {
      dead = true;
    };
  }, []);

  if (!loaded || !raw?.population) return null;

  return <PopulationCompositionBody population={raw.population} />;
}

function PopulationCompositionBody({ population }: { population: ResolvedCountPopulation }) {
  const effectiveRatio = percent(population.effective_n_ratio);

  return (
    <section data-testid="population-composition-panel" className="mt-6">
      <h2 className="text-lg font-black text-text">Population composition</h2>
      <p className="mt-1 text-sm text-muted">
        Server-reported composition for the scored forecast population used by the cluster gate.
      </p>

      <MotionReveal className="mt-4 rounded-2xl border border-border bg-surface p-4">
        <dl className="grid gap-3 sm:grid-cols-2">
          <Stat
            label="Effective-n estimate"
            value={numberLabel(population.effective_n_estimate)}
            hint="Correlation-cluster estimate reported by the API"
          />
          <Stat
            label="Effective-n ratio"
            value={effectiveRatio}
            hint="Effective sample relative to the nominal scored population"
          />
        </dl>

        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <ShareList title="Category shares" rows={population.category_histogram} />
          <ShareList title="Family shares" rows={population.family_histogram} />
        </div>
      </MotionReveal>
    </section>
  );
}

function ShareList({ title, rows }: { title: string; rows: PopulationHistogramEntry[] | null | undefined }) {
  if (!rows?.length) {
    return (
      <div className="rounded-xl border border-border bg-bg/40 p-3">
        <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{title}</h3>
        <p className="mt-2 text-xs text-muted-2">No histogram rows reported.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-bg/40 p-3">
      <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{title}</h3>
      <div className="mt-3 space-y-3">
        {rows.map((row) => (
          <ShareRow key={row.key} row={row} />
        ))}
      </div>
    </div>
  );
}

function ShareRow({ row }: { row: PopulationHistogramEntry }) {
  const value = Number.isFinite(row.share) ? row.share : null;
  const width = value === null ? 0 : Math.max(0, Math.min(100, value * 100));

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-xs">
        <span className="min-w-0 truncate font-medium text-text" title={row.key}>
          {row.key}
        </span>
        <span className="shrink-0 font-mono text-muted">{percent(value)}</span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3"
        role="progressbar"
        aria-label={`${row.key} share`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={width}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg/40 p-3">
      <dt className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted">{label}</dt>
      <dd className={cn("mt-1 font-mono text-lg font-bold", value === "—" ? "text-muted-2" : "text-text")}>
        {value}
      </dd>
      <p className="mt-0.5 text-[11px] text-muted-2">{hint}</p>
    </div>
  );
}

function numberLabel(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "—";
}

function percent(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}
