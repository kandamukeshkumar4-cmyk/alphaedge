"use client";

// S01: resolved-market review — a browsable, READ-ONLY public track record from
// GET /api/v1/resolved (backend O01). Every resolved market shows the model's
// prediction vs the REAL outcome with a per-market Brier; misses render as
// prominently as wins. Analysis only — this is NOT an order feed. Each row
// deep-links to the market detail.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildResolvedView,
  fetchResolved,
  type ResolvedResponse,
  type ResolvedRowView,
} from "@/lib/resolved-api";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { PageHeader, PageShell, StatRow, StatTile } from "@/components/ui/kit";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 25;
const intFmt = (n: number) => String(Math.round(n));
const pctFmt = (n: number) => `${Math.round(n * 100)}%`;
const brierFmt = (n: number) => n.toFixed(3);

function ResolvedRowCard({ row }: { row: ResolvedRowView }) {
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
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[11px] text-muted-2">
            <span className="truncate">{row.slug}</span>
            {row.resolvedLabel ? (
              <span>resolved {row.resolvedLabel}</span>
            ) : (
              <span className="text-muted-2">resolve date n/a</span>
            )}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-1 font-mono text-[11px] font-black",
            row.verdictTone === "up"
              ? "border-up/40 bg-up/10 text-up"
              : "border-danger/40 bg-danger/10 text-danger",
          )}
        >
          {row.verdictLabel}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-lg border px-2.5 py-1.5 font-mono text-xs font-black",
            row.outcomeTone === "up"
              ? "border-up/40 bg-up/10 text-up"
              : "border-danger/40 bg-danger/10 text-danger",
          )}
        >
          resolved {row.outcome}
        </span>
        <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-xs font-bold text-text">
          model {row.modelLabel}
        </span>
        <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-xs font-bold text-muted">
          Brier {row.brierLabel}
        </span>
      </div>
    </article>
  );
}

export default function ResolvedPage() {
  const [pages, setPages] = useState<ResolvedResponse[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [reachedEnd, setReachedEnd] = useState(false);

  const loadFirst = useCallback(async () => {
    setLoaded(false);
    setReachedEnd(false);
    const data = await fetchResolved({ limit: PAGE_SIZE, offset: 0 });
    setPages(data ? [data] : []);
    setReachedEnd(!data || data.rows.length < PAGE_SIZE);
    setLoaded(true);
  }, []);

  useEffect(() => {
    // Fetch-on-load + explicit "load more" only — no poll loop.
    void loadFirst();
  }, [loadFirst]);

  const loadMore = useCallback(async () => {
    if (loadingMore || reachedEnd) return;
    setLoadingMore(true);
    const offset = pages.reduce((sum, p) => sum + p.rows.length, 0);
    const data = await fetchResolved({ limit: PAGE_SIZE, offset });
    if (data && data.rows.length > 0) {
      setPages((prev) => [...prev, data]);
    }
    if (!data || data.rows.length < PAGE_SIZE) setReachedEnd(true);
    setLoadingMore(false);
  }, [loadingMore, reachedEnd, pages]);

  // Summary comes from the first page (it aggregates over ALL resolved markets).
  const summaryView = useMemo(
    () => buildResolvedView(pages[0] ?? null).summary,
    [pages],
  );
  const rows = useMemo(
    () => pages.flatMap((p) => buildResolvedView(p).rows),
    [pages],
  );
  const disclaimer = useMemo(
    () => buildResolvedView(pages[0] ?? null).disclaimer,
    [pages],
  );
  const reachable = pages.length > 0;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Public track record"
        title="Resolved-market review"
        subtitle="Every resolved market with the model's probability at close vs the REAL outcome, scored by a per-market Brier. Misses count as much as wins — nothing is curated. Read-only analysis; this is NOT an order feed."
        actions={
          <Link
            href="/track-record"
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold leading-10 text-text transition hover:border-accent hover:text-accent"
          >
            Calibration & CLV →
          </Link>
        }
      />

      <StatRow cols={3} className="mb-4">
        <StatTile
          label="Resolved markets"
          value={loaded ? <AnimatedNumber value={summaryView.n} format={intFmt} /> : "—"}
        />
        <StatTile
          label="Model accuracy"
          value={
            loaded && summaryView.accuracy !== null ? (
              <AnimatedNumber value={summaryView.accuracy} format={pctFmt} />
            ) : (
              "—"
            )
          }
          accent
        />
        <StatTile
          label="Mean Brier"
          value={
            loaded && summaryView.meanBrier !== null ? (
              <AnimatedNumber value={summaryView.meanBrier} format={brierFmt} />
            ) : (
              "—"
            )
          }
        />
      </StatRow>

      {loaded && summaryView.caveat ? (
        <div
          role="note"
          aria-label="Small sample caveat"
          className="mb-6 flex items-start gap-2 rounded-xl border border-gold/40 bg-secondary-dim px-4 py-3 text-sm text-text"
        >
          <span aria-hidden className="mt-0.5 text-gold">
            ⚠
          </span>
          <p className="font-semibold">{summaryView.caveat}</p>
        </div>
      ) : (
        <div className="mb-6" />
      )}

      {!loaded ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-2xl border border-border bg-surface"
            />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
          <p className="font-semibold text-text">
            {reachable ? "No resolved markets yet." : "The review is unreachable."}
          </p>
          <p className="mt-1">
            {reachable
              ? "The public track record fills in as real markets resolve — nothing is invented before then. Check back after the next resolutions."
              : "Live resolutions need the backend API. Once it is reachable, resolved markets appear here."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            {rows.map((row, i) => (
              <MotionReveal key={`${row.slug}-${i}`} delay={Math.min(i * 0.03, 0.24)}>
                <ResolvedRowCard row={row} />
              </MotionReveal>
            ))}
          </div>
          <div className="mt-6 flex justify-center">
            {reachedEnd ? (
              <p className="text-xs text-muted-2">
                End of resolved markets ({rows.length} shown).
              </p>
            ) : (
              <button
                type="button"
                onClick={() => void loadMore()}
                disabled={loadingMore}
                className="h-10 rounded-xl border border-border px-5 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:opacity-50"
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            )}
          </div>
        </>
      )}

      <p className="mt-6 text-xs text-muted-2">{disclaimer}</p>
    </PageShell>
  );
}
