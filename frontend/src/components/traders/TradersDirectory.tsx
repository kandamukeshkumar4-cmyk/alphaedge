"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader, PageShell, Panel, StatRow, StatTile } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import {
  fetchTraders,
  type TraderLeaderboardEntry,
  type TraderLeaderboardPage,
  type TraderSort,
} from "@/lib/traders-api";

const SORTS: Array<{
  value: TraderSort;
  label: string;
  shortLabel: string;
  explanation: string;
}> = [
  {
    value: "realized_pnl",
    label: "Realized paper P&L",
    shortLabel: "P&L",
    explanation:
      "Settled gains minus settled losses. Open paper positions do not move this rank.",
  },
  {
    value: "roi",
    label: "Return on paper capital",
    shortLabel: "ROI",
    explanation:
      "Realized paper P&L divided by capital risked on settled trades.",
  },
  {
    value: "win_rate",
    label: "Settled win rate",
    shortLabel: "Win rate",
    explanation:
      "The share of settled paper trades that resolved in the trader’s favor.",
  },
];

const currency = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
  signDisplay: "exceptZero",
});

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function metricValue(entry: TraderLeaderboardEntry, sort: TraderSort): string {
  if (sort === "roi") return formatPercent(entry.roi);
  if (sort === "win_rate") return formatPercent(entry.win_rate);
  return currency.format(entry.realized_pnl);
}

function initials(name: string): string {
  const cleaned = name.replace(/[^a-zA-Z0-9]/g, "");
  return cleaned.slice(0, 2).toUpperCase() || "TR";
}

function DirectorySkeleton() {
  return (
    <ul className="space-y-2" aria-label="Loading trader rankings" data-testid="traders-loading">
      {Array.from({ length: 7 }, (_, index) => (
        <li
          key={index}
          className="h-[88px] animate-pulse rounded-xl border border-border bg-surface-2/60"
        />
      ))}
    </ul>
  );
}

function TraderRow({
  entry,
  sort,
}: {
  entry: TraderLeaderboardEntry;
  sort: TraderSort;
}) {
  const sortLabel = SORTS.find((option) => option.value === sort)?.label ?? "rank";
  return (
    <li
      className="group grid min-h-[88px] grid-cols-[52px_minmax(0,1fr)] items-center gap-3 border-b border-border/70 px-3 py-3 last:border-0 sm:grid-cols-[64px_minmax(180px,1.2fr)_minmax(160px,1fr)_repeat(3,minmax(88px,.65fr))] sm:px-4"
      data-testid="trader-row"
    >
      <span className="font-mono text-xl font-black tabular-nums text-primary">
        #{entry.rank}
      </span>

      <span className="min-w-0">
        <span className="flex items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-border-light bg-surface-2 font-mono text-xs font-black text-text">
            {initials(entry.username)}
          </span>
          <span className="min-w-0">
            <Link
              href={`/traders/${encodeURIComponent(entry.username)}`}
              className="block truncate text-sm font-black text-text outline-none transition hover:text-primary focus-visible:rounded focus-visible:ring-2 focus-visible:ring-primary"
            >
              {entry.username}
            </Link>
            <span className="mt-1 block text-xs text-muted">
              Ranked #{entry.rank} by {sortLabel.toLocaleLowerCase()}
            </span>
          </span>
        </span>
      </span>

      <span className="col-span-2 rounded-lg border border-primary/25 bg-primary-dim/40 px-3 py-2 sm:col-span-1">
        <span className="block text-[10px] font-black uppercase tracking-[0.11em] text-muted-2">
          Ranking evidence
        </span>
        <span className="mt-0.5 block font-mono text-base font-black tabular-nums text-primary">
          {metricValue(entry, sort)}
        </span>
      </span>

      <span className="hidden text-right sm:block">
        <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
          Realized P&amp;L
        </span>
        <span
          className={cn(
            "font-mono text-sm font-bold tabular-nums",
            entry.realized_pnl >= 0 ? "text-primary" : "text-danger",
          )}
        >
          {currency.format(entry.realized_pnl)}
        </span>
      </span>

      <span className="hidden text-right sm:block">
        <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
          ROI / wins
        </span>
        <span className="font-mono text-sm tabular-nums text-text">
          {formatPercent(entry.roi)} / {formatPercent(entry.win_rate)}
        </span>
      </span>

      <span className="hidden text-right sm:block">
        <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
          Trades
        </span>
        <span className="font-mono text-sm tabular-nums text-text">
          {entry.total_trades.toLocaleString()}
        </span>
      </span>
    </li>
  );
}

export function TradersDirectory() {
  const [sort, setSort] = useState<TraderSort>("realized_pnl");
  const [query, setQuery] = useState("");
  const [data, setData] = useState<TraderLeaderboardPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchTraders(sort));
    } catch (cause) {
      setData(null);
      setError(
        cause instanceof Error
          ? cause.message
          : "The live trader rankings could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [sort]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  const visibleEntries = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return data?.entries ?? [];
    return (data?.entries ?? []).filter((entry) =>
      entry.username.toLocaleLowerCase().includes(needle),
    );
  }, [data, query]);

  const activeSort = SORTS.find((option) => option.value === sort) ?? SORTS[0];
  const listedTrades =
    data?.entries.reduce((sum, entry) => sum + entry.total_trades, 0) ?? 0;
  const profitableCount =
    data?.entries.filter((entry) => entry.realized_pnl > 0).length ?? 0;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Public paper record"
        title="Traders, with receipts"
        subtitle="See who has performed on settled paper markets and the exact metric behind every rank. Descriptive track records only—never execution advice."
        actions={
          <Link
            href="/leaderboard"
            className="inline-flex min-h-11 items-center rounded-xl border border-border bg-surface px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
          >
            Classic leaderboard
          </Link>
        }
      />

      <StatRow className="mb-5">
        <StatTile
          label="Ranked traders"
          value={loading ? "—" : (data?.total ?? 0).toLocaleString()}
          accent
          hint="Settled paper activity"
        />
        <StatTile
          label="Records shown"
          value={loading ? "—" : (data?.entries.length ?? 0).toLocaleString()}
          hint="Live API page"
        />
        <StatTile
          label="Trades in view"
          value={loading ? "—" : listedTrades.toLocaleString()}
          hint="Recorded paper orders"
        />
        <StatTile
          label="Positive P&L"
          value={loading ? "—" : profitableCount.toLocaleString()}
          hint="Among records shown"
        />
      </StatRow>

      <Panel className="mb-4" title="How the ranking works">
        <fieldset>
          <legend className="text-sm font-black text-text">
            Choose the evidence lens
          </legend>
          <p className="mt-1 text-xs leading-5 text-muted">{activeSort.explanation}</p>
          <ul className="mt-4 grid gap-2 sm:grid-cols-3" aria-label="Trader ranking metric">
            {SORTS.map((option) => {
              const active = option.value === sort;
              return (
                <li key={option.value}>
                  <button
                    type="button"
                    onClick={() => setSort(option.value)}
                    aria-pressed={active}
                    className={cn(
                      "min-h-11 w-full rounded-xl border px-3 py-2 text-left text-sm font-black outline-none transition focus-visible:ring-2 focus-visible:ring-primary",
                      active
                        ? "border-primary/50 bg-primary-dim text-primary"
                        : "border-border bg-surface-2/50 text-muted hover:border-border-light hover:text-text",
                    )}
                    data-testid={`trader-sort-${option.value}`}
                  >
                    {option.shortLabel}
                  </button>
                </li>
              );
            })}
          </ul>
        </fieldset>
      </Panel>

      <Panel
        padded={false}
        title={
          <span>
            Ranked records{" "}
            <span className="font-mono text-xs font-normal text-muted">
              {loading ? "" : `${visibleEntries.length} shown`}
            </span>
          </span>
        }
        action={
          <label className="sr-only" htmlFor="trader-search">
            Find a trader
          </label>
        }
      >
        <form
          className="border-b border-border p-3 sm:p-4"
          role="search"
          onSubmit={(event) => event.preventDefault()}
        >
          <label className="block text-[11px] font-black uppercase tracking-[0.1em] text-muted-2" htmlFor="trader-search">
            Find a trader
          </label>
          <input
            id="trader-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search the live ranking"
            className="mt-2 min-h-11 w-full rounded-xl border border-border bg-bg px-3 py-2 text-sm text-text outline-none transition placeholder:text-muted-2 focus:border-primary focus:ring-2 focus:ring-primary/25"
          />
        </form>

        <section className="min-h-[520px]" aria-live="polite">
          {loading ? (
            <section className="p-3 sm:p-4">
              <DirectorySkeleton />
            </section>
          ) : error ? (
            <section
              className="mx-auto flex min-h-[420px] max-w-lg flex-col items-center justify-center px-6 text-center"
              role="alert"
              data-testid="traders-error"
            >
              <span className="font-mono text-xs font-black uppercase tracking-[0.12em] text-danger">
                Live ranking unavailable
              </span>
              <h2 className="mt-3 text-xl font-black text-text">No stale standings shown</h2>
              <p className="mt-2 text-sm leading-6 text-muted">{error}</p>
              <button
                type="button"
                onClick={() => setReloadKey((value) => value + 1)}
                className="mt-5 min-h-11 rounded-xl bg-primary px-4 py-2 text-sm font-black text-bg outline-none transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-primary"
              >
                Retry live ranking
              </button>
            </section>
          ) : (data?.entries.length ?? 0) === 0 ? (
            <section
              className="mx-auto flex min-h-[420px] max-w-lg flex-col items-center justify-center px-6 text-center"
              data-testid="traders-empty"
            >
              <span className="font-mono text-xs font-black uppercase tracking-[0.12em] text-muted-2">
                Zero eligible records
              </span>
              <h2 className="mt-3 text-xl font-black text-text">No ranked traders yet</h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                A trader enters this list only after a paper trade settles. The surface stays
                empty until the live ledger has evidence.
              </p>
            </section>
          ) : visibleEntries.length === 0 ? (
            <section
              className="mx-auto flex min-h-[420px] max-w-lg flex-col items-center justify-center px-6 text-center"
              data-testid="traders-no-match"
            >
              <h2 className="text-xl font-black text-text">No matching trader</h2>
              <p className="mt-2 text-sm text-muted">
                Try another name or clear the search to return to all live records.
              </p>
              <button
                type="button"
                onClick={() => setQuery("")}
                className="mt-5 min-h-11 rounded-xl border border-border px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
              >
                Clear search
              </button>
            </section>
          ) : (
            <ul data-testid="traders-list">
              {visibleEntries.map((entry) => (
                <TraderRow key={entry.username} entry={entry} sort={sort} />
              ))}
            </ul>
          )}
        </section>
      </Panel>
    </PageShell>
  );
}
