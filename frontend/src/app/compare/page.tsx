"use client";

// S03: market comparison — a side-by-side of the desk's compact intelligence for
// 2-4 markets from GET /api/v1/compare?slugs= (backend O03). A picker adds
// markets via unified search typeahead + fetch-cache quick-picks; each column
// reuses the M02 share-snapshot view (price, model-vs-market edge, top signal
// with evidence, cross-venue arb flag, smart-money note). Honest per-column
// not-found. The columns row scrolls horizontally on narrow screens — it never
// clips, and the page itself never scrolls horizontally. Analysis only — NOT an
// order feed. Fetch-on-load / on-change only (no poll loop).
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  buildCompareView,
  fetchCompare,
  type CompareColumnView,
  type CompareResponse,
} from "@/lib/compare-api";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { searchUnified, type UnifiedSearchResult } from "@/lib/search-api";
import type { Market } from "@/lib/mock-data";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { PageHeader, PageShell } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";

const MAX = 4;
const pctFmt = (n: number) => `${Math.round(n * 100)}%`;
const intFmt = (n: number) => String(Math.round(n));

const EDGE_TONE: Record<"up" | "down" | "neutral", string> = {
  up: "text-up",
  down: "text-danger",
  neutral: "text-muted",
};

function CompareColumn({ col }: { col: CompareColumnView }) {
  const notFound = !col.found;
  return (
    <article
      className="flex w-[280px] shrink-0 flex-col rounded-2xl border border-border bg-surface p-4 sm:w-[300px]"
      aria-label={`Comparison column for ${col.title || col.requestedSlug}`}
    >
      <div className="min-w-0">
        <Link
          href={marketHref(col.requestedSlug)}
          className="block break-words text-sm font-bold text-text hover:text-primary hover:underline"
        >
          {col.title || col.requestedSlug}
        </Link>
        <p className="mt-0.5 break-all font-mono text-[11px] text-muted-2">{col.requestedSlug}</p>
      </div>

      {notFound ? (
        <p className="mt-4 rounded-lg border border-dashed border-border bg-surface-2 px-3 py-4 text-xs text-muted">
          No intelligence for this market — it is not in the desk catalog, so nothing is
          fabricated for this column.
        </p>
      ) : (
        <>
          <div className="mt-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">YES price</p>
            {col.yesPrice !== null ? (
              <p className="mt-1 font-mono text-2xl font-black tabular-nums text-text">
                <AnimatedNumber value={col.yesPrice} format={pctFmt} />
              </p>
            ) : (
              <p className="mt-1 text-xs text-muted-2">No odds snapshot yet</p>
            )}
          </div>

          <div className="mt-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
              Forecast vs market
            </p>
            {col.edgeLabel || col.modelLabel ? (
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs font-bold">
                {col.modelLabel ? <span className="text-text">forecast {col.modelLabel}</span> : null}
                {col.marketLabel ? <span className="text-muted">market {col.marketLabel}</span> : null}
                {col.edgeLabel ? (
                  <span className={cn("font-black", EDGE_TONE[col.edgeTone])}>edge {col.edgeLabel}</span>
                ) : null}
              </p>
            ) : (
              <p className="mt-1 text-xs text-muted-2">No model prediction logged</p>
            )}
          </div>

          <div className="mt-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Cross-venue arb</p>
            {col.arbMatched ? (
              <span className="mt-1 inline-flex items-center rounded-lg border border-accent/40 bg-accent/12 px-2 py-0.5 font-mono text-[11px] font-black text-accent">
                Match found
              </span>
            ) : (
              <p className="mt-1 text-xs text-muted-2">No arb match</p>
            )}
          </div>

          <div className="mt-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Smart money</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              {col.smartMoneyNote ?? <span className="text-muted-2">No smart-money activity.</span>}
            </p>
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-2">
              <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Top signal</p>
              {col.topSignal ? (
                <span className="rounded bg-accent-dim px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-accent-bright">
                  {col.topSignal.familyLabel}
                </span>
              ) : null}
            </div>
            {col.topSignal ? (
              <>
                <p className="mt-1.5 text-[11px] font-bold uppercase tracking-wide text-text">
                  {col.topSignal.typeLabel}
                </p>
                {col.topSignal.evidence ? (
                  <SignalEvidenceBlock evidence={col.topSignal.evidence} />
                ) : null}
              </>
            ) : (
              <p className="mt-1.5 text-xs text-muted-2">No signals yet.</p>
            )}
          </div>
        </>
      )}

      <div className="mt-auto border-t border-border pt-3">
        <Link
          href={marketHref(col.requestedSlug)}
          className="text-[11px] font-semibold text-accent hover:underline"
        >
          Open market →
        </Link>
      </div>
    </article>
  );
}

export default function ComparePage() {
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UnifiedSearchResult[]>([]);
  const [quickPicks, setQuickPicks] = useState<Market[]>([]);
  const [raw, setRaw] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Quick-picks from the shared markets fetch-cache (no extra raw poll loop).
  useEffect(() => {
    let alive = true;
    void fetchMarkets({}).then((markets) => {
      if (alive) setQuickPicks(markets.slice(0, 8));
    });
    return () => {
      alive = false;
    };
  }, []);

  // Debounced unified search typeahead.
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults([]);
      return;
    }
    const ctrl = new AbortController();
    const t = window.setTimeout(() => {
      void searchUnified(q, 6, ctrl.signal)
        .then(setResults)
        .catch(() => {
          if (!ctrl.signal.aborted) setResults([]);
        });
    }, 220);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [query]);

  // Fetch the comparison whenever the selection changes.
  const selKey = selected.join(",");
  const lastFetched = useRef<string>("");
  useEffect(() => {
    if (selected.length === 0) {
      setRaw(null);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    lastFetched.current = selKey;
    void fetchCompare(selected, { signal: ctrl.signal }).then((data) => {
      if (ctrl.signal.aborted || lastFetched.current !== selKey) return;
      setRaw(data);
      setLoading(false);
    });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selKey]);

  function addSlug(slug: string) {
    setSelected((prev) =>
      prev.includes(slug) || prev.length >= MAX ? prev : [...prev, slug],
    );
    setQuery("");
    setResults([]);
  }

  function removeSlug(slug: string) {
    setSelected((prev) => prev.filter((s) => s !== slug));
  }

  const view = useMemo(() => buildCompareView(raw), [raw]);
  const atMax = selected.length >= MAX;

  return (
    <PageShell width="wide">
      <PageHeader
        kicker="Side-by-side"
        title="Compare markets"
        subtitle="Add 2-4 markets to line up the desk's compact intelligence column by column: YES price, model-vs-market edge, cross-venue arb, smart money, and the top signal with evidence. Read-only analysis — this is NOT an order feed."
        actions={
          <span className="rounded-pill border border-border px-3 py-1 font-mono text-[11px] font-bold text-muted-2">
            <AnimatedNumber value={selected.length} format={intFmt} /> / {MAX} selected
          </span>
        }
      />

      {/* Picker */}
      <section aria-label="Market picker" className="mb-6 rounded-2xl border border-border bg-surface p-4 sm:p-5">
        <label htmlFor="compare-search" className="text-[11px] font-black uppercase tracking-[0.08em] text-muted-2">
          Add a market
        </label>
        <div className="relative mt-2">
          <input
            id="compare-search"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={atMax}
            placeholder={atMax ? "Maximum of 4 markets selected" : "Search markets to compare…"}
            aria-label="Search markets to compare"
            autoComplete="off"
            className="h-11 w-full rounded-xl border border-border bg-bg px-3.5 text-sm text-text outline-none transition placeholder:text-muted-2 focus:border-accent disabled:opacity-50"
          />
          {results.length > 0 && !atMax ? (
            <ul
              role="listbox"
              aria-label="Search results"
              className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-xl border border-border bg-surface p-1 shadow-lift"
            >
              {results.map((r) => {
                const already = selected.includes(r.slug);
                return (
                  <li key={r.slug}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={already}
                      disabled={already}
                      onClick={() => addSlug(r.slug)}
                      className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-surface-2 disabled:opacity-40"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-text">{r.title}</span>
                        <span className="block truncate font-mono text-[11px] text-muted-2">{r.slug}</span>
                      </span>
                      <span className="shrink-0 text-[11px] font-bold text-accent">
                        {already ? "Added" : "Add +"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>

        {/* Quick picks */}
        {quickPicks.length > 0 && !atMax ? (
          <div className="mt-3">
            <p className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">Quick picks</p>
            <div className="no-scrollbar mt-1.5 flex gap-1.5 overflow-x-auto">
              {quickPicks.map((m) => (
                <button
                  key={m.slug}
                  type="button"
                  disabled={selected.includes(m.slug)}
                  onClick={() => addSlug(m.slug)}
                  className="shrink-0 whitespace-nowrap rounded-pill border border-border bg-surface px-3 py-1.5 text-xs font-bold text-muted transition hover:border-accent hover:text-accent disabled:opacity-40"
                >
                  {m.title.length > 28 ? `${m.title.slice(0, 28)}…` : m.title}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {/* Selected chips */}
        {selected.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {selected.map((slug) => (
              <span
                key={slug}
                className="inline-flex items-center gap-2 rounded-pill border border-accent/40 bg-accent/10 px-3 py-1.5 font-mono text-xs font-bold text-accent"
              >
                <span className="max-w-[180px] truncate">{slug}</span>
                <button
                  type="button"
                  onClick={() => removeSlug(slug)}
                  aria-label={`Remove ${slug} from comparison`}
                  className="text-accent/80 transition hover:text-accent"
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        ) : null}
      </section>

      {/* Columns */}
      {selected.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          <p className="font-semibold text-text">No markets selected yet.</p>
          <p className="mt-1">Add 2-4 markets above to line them up side by side.</p>
        </div>
      ) : loading && view.columns.length === 0 ? (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {selected.map((slug) => (
            <div
              key={slug}
              className="h-80 w-[280px] shrink-0 animate-pulse rounded-2xl border border-border bg-surface sm:w-[300px]"
            />
          ))}
        </div>
      ) : !view.reachable ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
          <p className="font-semibold text-text">The comparison is unreachable.</p>
          <p className="mt-1">Live intelligence needs the backend API. Once reachable, the columns appear here.</p>
        </div>
      ) : (
        <>
          {view.clamped ? (
            <p role="note" className="mb-3 text-xs text-muted-2">
              Only the first {view.maxSlugs} markets are compared.
            </p>
          ) : null}
          {/* The columns get their OWN horizontal scroll container — the page never scrolls sideways. */}
          <div
            className="flex gap-3 overflow-x-auto pb-2"
            role="group"
            aria-label="Market comparison columns"
          >
            {view.columns.map((col, i) => (
              <MotionReveal
                key={col.requestedSlug}
                delay={Math.min(i * 0.05, 0.2)}
                className="shrink-0"
              >
                <CompareColumn col={col} />
              </MotionReveal>
            ))}
          </div>
        </>
      )}

      <p className="mt-6 text-xs text-muted-2">{view.disclaimer}</p>
    </PageShell>
  );
}
