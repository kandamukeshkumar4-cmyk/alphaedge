"use client";

// R01: opportunity scanner — a ranked, READ-ONLY "biggest edges right now" view
// from GET /api/v1/opportunities (backend N01). Analysis only: this is NOT an
// order feed and never presents a bet/execute CTA. Each row deep-links to the
// market detail (where the existing trade panel lives) as a paper-trade path.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  buildOpportunitiesView,
  fetchOpportunities,
  type DirectionFilter,
  type OpportunitiesResponse,
  type OpportunityRowView,
} from "@/lib/opportunities-api";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { PageHeader, PageShell, SegTabs, StatRow, StatTile } from "@/components/ui/kit";
import { cn } from "@/lib/cn";

const DIRECTION_OPTIONS: { value: DirectionFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "YES", label: "YES lean" },
  { value: "NO", label: "NO lean" },
];

const LIQUIDITY_STEPS: { value: number; label: string }[] = [
  { value: 0, label: "Any" },
  { value: 1_000, label: "1K+" },
  { value: 10_000, label: "10K+" },
  { value: 100_000, label: "100K+" },
];

const intFmt = (n: number) => String(Math.round(n));
const ptsFmt = (n: number) => `${(n * 100).toFixed(1)} pts`;

function OpportunityCard({ row }: { row: OpportunityRowView }) {
  return (
    <article className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={row.href}
            className="block truncate text-sm font-bold text-text hover:text-primary hover:underline"
          >
            {row.title}
          </Link>
          <p className="mt-0.5 truncate font-mono text-[11px] text-muted-2">{row.slug}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-1 font-mono text-[11px] font-black",
            row.directionTone === "up"
              ? "border-up/40 bg-up/10 text-up"
              : "border-danger/40 bg-danger/10 text-danger",
          )}
        >
          {row.direction} lean
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-lg border border-accent/40 bg-accent/12 px-2.5 py-1.5 font-mono text-sm font-black text-accent">
          edge{" "}
          <AnimatedNumber value={row.edge} format={ptsFmt} />
        </span>
        <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-xs font-bold text-text">
          model {row.modelLabel}
        </span>
        <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-xs font-bold text-muted">
          market {row.marketLabel}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-muted-2">
        <span>
          YES price {row.yesPriceLabel ?? <span className="text-muted-2">n/a</span>}
        </span>
        <span>liquidity {row.liquidityLabel}</span>
        {row.family ? <span className="text-accent">{row.family}</span> : null}
      </div>

      {row.evidence ? <SignalEvidenceBlock evidence={row.evidence} /> : null}

      <div className="mt-3 border-t border-border pt-3">
        <Link
          href={row.href}
          className="text-[11px] font-semibold text-accent hover:underline"
        >
          Open market & paper-trade panel →
        </Link>
      </div>
    </article>
  );
}

export default function OpportunitiesPage() {
  const [raw, setRaw] = useState<OpportunitiesResponse | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [direction, setDirection] = useState<DirectionFilter>("all");
  const [minLiquidity, setMinLiquidity] = useState(0);

  async function load() {
    setLoaded(false);
    const data = await fetchOpportunities({ limit: 50 });
    setRaw(data);
    setLoaded(true);
  }

  useEffect(() => {
    // Fetch-on-load only; direction + min-liquidity filter the fetched set
    // client-side (no extra requests, no poll loop).
    void load();
  }, []);

  const view = useMemo(
    () => buildOpportunitiesView(raw, { direction, minLiquidity }),
    [raw, direction, minLiquidity],
  );

  const topEdge = view.rows[0]?.edge ?? 0;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Opportunity scanner"
        title="Biggest edges right now"
        subtitle="Markets ranked by how far the model's probability sits from the market price. Ranked read-only analysis — this is NOT an order feed; open a market to reach its paper-trade panel."
        actions={
          <button
            type="button"
            onClick={() => void load()}
            disabled={!loaded}
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
          >
            {loaded ? "Refresh" : "Refreshing…"}
          </button>
        }
      />

      <StatRow cols={3} className="mb-6">
        <StatTile
          label="Ranked edges"
          value={loaded ? <AnimatedNumber value={view.totalBeforeFilter} format={intFmt} /> : "—"}
        />
        <StatTile
          label="Shown after filter"
          value={loaded ? <AnimatedNumber value={view.count} format={intFmt} /> : "—"}
          accent
        />
        <StatTile
          label="Top edge"
          value={loaded && view.rows.length > 0 ? <AnimatedNumber value={topEdge} format={ptsFmt} /> : "—"}
        />
      </StatRow>

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">
            Direction lean
          </span>
          <SegTabs
            value={direction}
            onChange={setDirection}
            options={DIRECTION_OPTIONS}
            size="sm"
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">
            Min liquidity
          </span>
          <SegTabs
            value={String(minLiquidity)}
            onChange={(v) => setMinLiquidity(Number(v))}
            options={LIQUIDITY_STEPS.map((s) => ({ value: String(s.value), label: s.label }))}
            size="sm"
          />
        </div>
      </div>

      {!loaded ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-44 animate-pulse rounded-2xl border border-border bg-surface" />
          ))}
        </div>
      ) : view.rows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
          <p className="font-semibold text-text">No opportunities meet the filter right now.</p>
          <p className="mt-1">
            {raw === null
              ? "The scanner is unreachable — live edges need the backend API."
              : view.totalBeforeFilter === 0
                ? "No open market currently has both a model probability and a market price to rank — edges appear only from real predictions, never fabricated."
                : "Every ranked edge was filtered out by the current direction / min-liquidity controls. Loosen a filter to see more."}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {view.rows.map((row, i) => (
            <MotionReveal key={row.slug} delay={Math.min(i * 0.04, 0.24)}>
              <OpportunityCard row={row} />
            </MotionReveal>
          ))}
        </div>
      )}

      <p className="mt-6 text-xs text-muted-2">{view.disclaimer}</p>
    </PageShell>
  );
}
