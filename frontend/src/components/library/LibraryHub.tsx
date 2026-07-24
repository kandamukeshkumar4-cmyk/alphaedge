"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LibraryCard } from "@/components/library/LibraryCard";
import { PageHeader, PageShell, Panel, StatRow, StatTile } from "@/components/ui/kit";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  loadLibrary,
  type LibraryItem,
  type LibraryKind,
  type LibraryResult,
  type LibrarySource,
} from "@/lib/library-api";

type Filter = "all" | LibraryKind;
type SortOrder = "newest" | "oldest";

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "All" },
  { value: "brief", label: "Briefs" },
  { value: "report", label: "Reports" },
  { value: "scanner", label: "Scans" },
  { value: "alpha", label: "Alpha runs" },
  { value: "workflow", label: "Workflows" },
];

const SOURCE_LABELS: Record<LibrarySource, string> = {
  briefs: "Briefs",
  memories: "Resolved memory",
  scanners: "Scanners",
  alpha: "Alpha",
  skills: "Workflows",
};

function LibrarySkeleton() {
  return (
    <ul aria-label="Loading research library" data-testid="library-loading">
      {Array.from({ length: 5 }, (_, index) => (
        <li key={index} className="border-b border-border/70 p-4 last:border-0 sm:p-5">
          <span className="block h-20 animate-pulse rounded-xl bg-surface-2" />
        </li>
      ))}
    </ul>
  );
}

function sourceCount(result: LibraryResult | null): number {
  if (!result) return 0;
  return Object.values(result.sources).filter((status) => status !== "error").length;
}

export function LibraryHub() {
  const { token, isReady } = useAuth();
  const [result, setResult] = useState<LibraryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    if (!isReady) return;
    setLoading(true);
    setFatalError(null);
    try {
      const next = await loadLibrary(token);
      setResult(next);
      if (next.failedSources.length === 5 && next.items.length === 0) {
        setFatalError("None of the live research sources responded.");
      }
    } catch (cause) {
      setResult(null);
      setFatalError(
        cause instanceof Error ? cause.message : "The live research library is unavailable.",
      );
    } finally {
      setLoading(false);
    }
  }, [isReady, token]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  const visibleItems = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const items = (result?.items ?? []).filter((item) => {
      if (filter !== "all" && item.kind !== filter) return false;
      if (!needle) return true;
      return [item.title, item.summary, item.label, item.status, ...item.details]
        .filter((value): value is string => typeof value === "string")
        .some((value) => value.toLocaleLowerCase().includes(needle));
    });
    return items.sort((left, right) => {
      const leftTime = left.timestamp ? new Date(left.timestamp).getTime() : 0;
      const rightTime = right.timestamp ? new Date(right.timestamp).getTime() : 0;
      const delta =
        (Number.isNaN(rightTime) ? 0 : rightTime) -
        (Number.isNaN(leftTime) ? 0 : leftTime);
      return sortOrder === "newest" ? delta : -delta;
    });
  }, [filter, query, result, sortOrder]);

  const counts = useMemo(() => {
    const items = result?.items ?? [];
    return {
      total: items.length,
      briefs: items.filter((item) => item.kind === "brief").length,
      reports: items.filter((item) => item.kind === "report").length,
      automated: items.filter(
        (item) => item.kind === "scanner" || item.kind === "alpha",
      ).length,
    };
  }, [result]);

  const partialFailures = result?.failedSources ?? [];
  const hasItems = (result?.items.length ?? 0) > 0;

  return (
    <PageShell width="medium" className="pb-12" >
      <section data-testid="library-hub">
        <PageHeader
          kicker="Persisted research"
          title="Library"
          subtitle="Browse the briefs, resolved reports, scanner results, alpha runs, and research workflows currently stored by AlphaEdge. Every card comes from a live read."
          actions={
            <Link
              href="/research"
              className="inline-flex min-h-11 items-center rounded-xl border border-border bg-surface px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
            >
              Open research feed
            </Link>
          }
        />

        <StatRow className="mb-5">
          <StatTile
            label="Artifacts"
            value={loading ? "—" : counts.total.toLocaleString()}
            accent
            hint="Across live sources"
          />
          <StatTile
            label="Briefs"
            value={loading ? "—" : counts.briefs.toLocaleString()}
            hint="Analyst research"
          />
          <StatTile
            label="Resolved reports"
            value={loading ? "—" : counts.reports.toLocaleString()}
            hint="Graded market memory"
          />
          <StatTile
            label="Automated runs"
            value={loading ? "—" : counts.automated.toLocaleString()}
            hint="Scanner + alpha"
          />
        </StatRow>

        <Panel className="mb-4" title="Live source index">
          <ul className="grid gap-2 sm:grid-cols-5" aria-label="Library source status">
            {(Object.keys(SOURCE_LABELS) as LibrarySource[]).map((source) => {
              const status = result?.sources[source] ?? "empty";
              return (
                <li
                  key={source}
                  className="flex min-h-11 items-center justify-between rounded-xl border border-border bg-surface-2/50 px-3 py-2"
                >
                  <span className="text-xs font-bold text-text">{SOURCE_LABELS[source]}</span>
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      loading
                        ? "animate-pulse bg-muted-2"
                        : status === "error"
                          ? "bg-danger"
                          : status === "ready"
                            ? "bg-primary"
                            : "bg-muted-2",
                    )}
                    aria-label={loading ? "Loading" : status}
                  />
                </li>
              );
            })}
          </ul>
          <p className="mt-3 font-mono text-[11px] text-muted-2">
            {loading
              ? "Checking persisted sources…"
              : `${sourceCount(result)} of 5 live sources responded.`}
          </p>
        </Panel>

        {partialFailures.length > 0 && partialFailures.length < 5 ? (
          <p
            className="mb-4 rounded-xl border border-gold/30 bg-gold/10 px-4 py-3 text-sm text-text"
            role="status"
            data-testid="library-partial-error"
          >
            Partial live result:{" "}
            {partialFailures.map((source) => SOURCE_LABELS[source]).join(", ")} did not
            respond. Available artifacts remain browsable.
          </p>
        ) : null}

        <Panel
          padded={false}
          title={
            <span>
              Research archive{" "}
              <span className="font-mono text-xs font-normal text-muted">
                {loading ? "" : `${visibleItems.length} shown`}
              </span>
            </span>
          }
        >
          <form
            className="grid gap-3 border-b border-border p-3 sm:grid-cols-[minmax(220px,1fr)_180px] sm:p-4"
            role="search"
            onSubmit={(event) => event.preventDefault()}
          >
            <label className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-2" htmlFor="library-search">
              Find research
              <input
                id="library-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search title, market, status, or evidence"
                className="mt-2 block min-h-11 w-full rounded-xl border border-border bg-bg px-3 py-2 text-sm font-normal normal-case tracking-normal text-text outline-none transition placeholder:text-muted-2 focus:border-primary focus:ring-2 focus:ring-primary/25"
              />
            </label>
            <label className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-2" htmlFor="library-sort">
              Sort
              <select
                id="library-sort"
                value={sortOrder}
                onChange={(event) => setSortOrder(event.target.value as SortOrder)}
                className="mt-2 block min-h-11 w-full rounded-xl border border-border bg-bg px-3 py-2 text-sm font-bold normal-case tracking-normal text-text outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/25"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </label>
          </form>

          <nav className="overflow-x-auto border-b border-border px-3 py-3 sm:px-4" aria-label="Filter research by type">
            <ul className="flex min-w-max gap-1.5">
              {FILTERS.map((option) => {
                const active = filter === option.value;
                return (
                  <li key={option.value}>
                    <button
                      type="button"
                      onClick={() => setFilter(option.value)}
                      aria-pressed={active}
                      className={cn(
                        "min-h-11 rounded-xl border px-3.5 py-2 text-sm font-black outline-none transition focus-visible:ring-2 focus-visible:ring-primary",
                        active
                          ? "border-primary/50 bg-primary-dim text-primary"
                          : "border-border bg-surface text-muted hover:border-border-light hover:text-text",
                      )}
                      data-testid={`library-filter-${option.value}`}
                    >
                      {option.label}
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          <section className="min-h-[520px]" aria-live="polite">
            {loading ? (
              <LibrarySkeleton />
            ) : fatalError ? (
              <section
                className="mx-auto flex min-h-[460px] max-w-lg flex-col items-center justify-center px-6 text-center"
                role="alert"
                data-testid="library-error"
              >
                <span className="font-mono text-xs font-black uppercase tracking-[0.12em] text-danger">
                  Live archive unavailable
                </span>
                <h2 className="mt-3 text-xl font-black text-text">No sample artifacts substituted</h2>
                <p className="mt-2 text-sm leading-6 text-muted">{fatalError}</p>
                <button
                  type="button"
                  onClick={() => setReloadKey((value) => value + 1)}
                  className="mt-5 min-h-11 rounded-xl bg-primary px-4 py-2 text-sm font-black text-bg outline-none transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Retry live sources
                </button>
              </section>
            ) : !hasItems ? (
              <section
                className="mx-auto flex min-h-[460px] max-w-lg flex-col items-center justify-center px-6 text-center"
                data-testid="library-empty"
              >
                <span className="font-mono text-xs font-black uppercase tracking-[0.12em] text-muted-2">
                  Archive is empty
                </span>
                <h2 className="mt-3 text-xl font-black text-text">No persisted research yet</h2>
                <p className="mt-2 text-sm leading-6 text-muted">
                  Briefs, resolved memories, completed scanner work, alpha runs, and
                  saved workflows will appear here when their live sources contain data.
                </p>
                <Link
                  href="/research"
                  className="mt-5 inline-flex min-h-11 items-center rounded-xl border border-border px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Open research feed
                </Link>
              </section>
            ) : visibleItems.length === 0 ? (
              <section
                className="mx-auto flex min-h-[460px] max-w-lg flex-col items-center justify-center px-6 text-center"
                data-testid="library-no-match"
              >
                <h2 className="text-xl font-black text-text">Nothing matches this view</h2>
                <p className="mt-2 text-sm text-muted">
                  Change the type filter or clear the search to see the full live archive.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setFilter("all");
                    setQuery("");
                  }}
                  className="mt-5 min-h-11 rounded-xl border border-border px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Reset filters
                </button>
              </section>
            ) : (
              <ul data-testid="library-list">
                {visibleItems.map((item: LibraryItem) => (
                  <LibraryCard key={item.id} item={item} />
                ))}
              </ul>
            )}
          </section>
        </Panel>

        <p className="mt-5 text-xs leading-5 text-muted-2">
          Library artifacts are read-only research records. They cannot place, size, or
          execute an order.
        </p>
      </section>
    </PageShell>
  );
}
