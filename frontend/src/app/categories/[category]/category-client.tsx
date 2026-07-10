"use client";

// S02: category intelligence dashboard — a per-category aggregate from GET
// /api/v1/categories/{category}/summary (backend O02): market count, mean
// absolute edge, top N01 opportunities (reusing the shared OpportunityCard),
// recent signal count, and the O01 resolved-market accuracy. Honest
// unreachable / {found:false} states — nothing is fabricated. Analysis only.
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  buildCategorySummaryView,
  fetchCategorySummary,
  type CategorySummaryResponse,
} from "@/lib/category-summary-api";
import { OpportunityCard } from "@/components/OpportunityCard";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { PageHeader, PageShell, StatRow, StatTile } from "@/components/ui/kit";

const intFmt = (n: number) => String(Math.round(n));
const pctFmt = (n: number) => `${Math.round(n * 100)}%`;
const ptsFmt = (n: number) => `${(n * 100).toFixed(1)} pts`;

function readCategory(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export default function CategoryDashboardClient() {
  const params = useParams();
  const category = readCategory(params?.category as string | string[] | undefined);

  const [raw, setRaw] = useState<CategorySummaryResponse | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    // Fetch-on-load only — no poll loop.
    void fetchCategorySummary(category).then((data) => {
      if (!alive) return;
      setRaw(data);
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, [category]);

  const view = useMemo(
    () => buildCategorySummaryView(raw, category),
    [raw, category],
  );

  const showEmpty = loaded && (!view.reachable || !view.found);

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Category intelligence"
        title={category || "Category"}
        subtitle="A per-category read-only aggregate: how far the model sits from the market, where the biggest edges are, how active the signals are, and how the model has actually done on resolved markets in this category. Analysis only — this is NOT an order feed."
        actions={
          <Link
            href="/markets"
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold leading-10 text-text transition hover:border-accent hover:text-accent"
          >
            ← All markets
          </Link>
        }
      />

      <StatRow cols={4} className="mb-6">
        <StatTile
          label="Markets"
          value={loaded ? <AnimatedNumber value={view.marketCount} format={intFmt} /> : "—"}
        />
        <StatTile
          label="Mean edge"
          value={
            loaded && view.meanAbsEdge !== null ? (
              <AnimatedNumber value={view.meanAbsEdge} format={ptsFmt} />
            ) : (
              "—"
            )
          }
          accent
        />
        <StatTile
          label="Signals (7d)"
          value={loaded ? <AnimatedNumber value={view.recentSignalCount} format={intFmt} /> : "—"}
        />
        <StatTile
          label="Resolved accuracy"
          value={
            loaded && view.resolvedAccuracy !== null ? (
              <AnimatedNumber value={view.resolvedAccuracy} format={pctFmt} />
            ) : (
              "—"
            )
          }
          hint={loaded && view.resolvedN > 0 ? `n=${view.resolvedN}` : "no resolves yet"}
        />
      </StatRow>

      {!loaded ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-44 animate-pulse rounded-2xl border border-border bg-surface"
            />
          ))}
        </div>
      ) : showEmpty ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
          <p className="font-semibold text-text">
            {view.reachable
              ? `No data for “${category}”.`
              : "The category dashboard is unreachable."}
          </p>
          <p className="mt-1">
            {view.reachable
              ? "This category has no local markets and no resolved markets yet — nothing is invented to fill the gap. Try another category from the markets board."
              : "Live category intelligence needs the backend API. Once it is reachable, the aggregate appears here."}
          </p>
        </div>
      ) : (
        <section>
          <div className="mb-3 flex items-end justify-between gap-3">
            <h2 className="text-base font-black tracking-tight text-text sm:text-lg">
              Top edges in {category}
            </h2>
            <Link
              href="/opportunities"
              className="text-xs font-semibold text-accent hover:underline"
            >
              Full scanner →
            </Link>
          </div>
          {view.topOpportunities.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-6 text-sm text-muted">
              <p className="font-semibold text-text">No ranked edges in this category right now.</p>
              <p className="mt-1">
                Edges appear only from real model-vs-market disagreement — none is currently
                open in {category}.
              </p>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {view.topOpportunities.map((row, i) => (
                <MotionReveal key={row.slug} delay={Math.min(i * 0.04, 0.2)}>
                  <OpportunityCard row={row} />
                </MotionReveal>
              ))}
            </div>
          )}
        </section>
      )}

      <p className="mt-6 text-xs text-muted-2">{view.disclaimer}</p>
    </PageShell>
  );
}
