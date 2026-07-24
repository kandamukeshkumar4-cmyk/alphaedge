"use client";

/**
 * Loop V85 (L2) — Screener page shell.
 *
 * Filter bar (category, min volume, min edge, hours-to-close, sort) feeds the
 * `@/lib/screener-api` live-first client (mock fallback). Results render as a
 * dense, sortable table: mono numerals, sticky header, row hover. The model
 * edge column is tinted mint (positive) / blue (negative) — never red, per the
 * V85 binding theme. Skeleton shimmer while loading, empty state when the
 * filtered set is empty, horizontal scroll container on mobile.
 *
 * PAPER_TRADING_ONLY — read-only research surface; no order path.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";
import {
  formatHours,
  formatPercent,
  formatPrice,
  formatVolume,
  listScreener,
  sortItems,
  type ScreenerFilters,
  type ScreenerItem,
  type ScreenerSort,
} from "@/lib/screener-api";

const CATEGORIES = [
  { value: "all", label: "All categories" },
  { value: "nba", label: "NBA" },
  { value: "election", label: "Elections" },
  { value: "crypto", label: "Crypto" },
  { value: "culture", label: "Culture" },
] as const;

const SORTS: { value: ScreenerSort; label: string }[] = [
  { value: "edge", label: "Edge (|model − market|)" },
  { value: "volume", label: "Volume" },
  { value: "move", label: "24h move" },
  { value: "closing", label: "Closing soon" },
];

const SKELETON_ROWS = 6;

export function ScreenerShell() {
  const { token, isReady } = useAuth();
  const [items, setItems] = useState<ScreenerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<"live" | "mock">("mock");

  const [category, setCategory] = useState<string>("all");
  const [minVolume, setMinVolume] = useState<string>("");
  const [minEdge, setMinEdge] = useState<string>("");
  const [maxHours, setMaxHours] = useState<string>("");
  const [sort, setSort] = useState<ScreenerSort>("edge");

  const filters: ScreenerFilters = useMemo(
    () => ({
      category: category === "all" ? undefined : category,
      min_volume: minVolume.trim() ? Number(minVolume) : undefined,
      min_edge: minEdge.trim() ? Number(minEdge) : undefined,
      max_hours_to_close: maxHours.trim() ? Number(maxHours) : undefined,
      sort,
    }),
    [category, minVolume, minEdge, maxHours, sort],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { result, source: src } = await listScreener(
        filters,
        isReady ? token : null,
      );
      setItems(result.items);
      setTotal(result.total);
      setSource(src);
    } finally {
      setLoading(false);
    }
  }, [filters, isReady, token]);

  useEffect(() => {
    if (!isReady) return;
    const handle = setTimeout(() => void refresh(), 180);
    return () => clearTimeout(handle);
  }, [isReady, refresh]);

  // Local re-sort on header click (the mock already sorts server-side, but the
  // live endpoint may return pre-sorted rows — re-sort client-side so the
  // clicked column is always authoritative without a refetch).
  const sortedItems = useMemo(() => sortItems(items, sort), [items, sort]);

  const hasFilters =
    category !== "all" ||
    minVolume.trim() !== "" ||
    minEdge.trim() !== "" ||
    maxHours.trim() !== "";

  return (
    <div data-testid="screener-shell">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-text sm:text-3xl">
            Screener
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Live paper markets ranked by model-vs-market edge. Filter, sort, and
            jump straight into a market. {PAPER_TRADING_DISCLAIMER}
          </p>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
          {source === "live" ? "live feed" : "local mock"} · {total} markets
        </span>
      </div>
      {!loading && source === "mock" ? (
        <p className="mb-4 text-center text-xs text-muted-2">
          Showing demo screener data. Connect the API to rank live paper markets.
        </p>
      ) : null}

      <FilterBar
        category={category}
        setCategory={setCategory}
        minVolume={minVolume}
        setMinVolume={setMinVolume}
        minEdge={minEdge}
        setMinEdge={setMinEdge}
        maxHours={maxHours}
        setMaxHours={setMaxHours}
        sort={sort}
        setSort={setSort}
      />

      <div className="mt-4 overflow-x-auto rounded-2xl border border-border bg-surface">
        {loading ? (
          <ScreenerSkeleton />
        ) : sortedItems.length === 0 ? (
          <EmptyState hasFilters={hasFilters} />
        ) : (
          <ScreenerTable items={sortedItems} sort={sort} onSort={setSort} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

function FilterBar(props: {
  category: string;
  setCategory: (v: string) => void;
  minVolume: string;
  setMinVolume: (v: string) => void;
  minEdge: string;
  setMinEdge: (v: string) => void;
  maxHours: string;
  setMaxHours: (v: string) => void;
  sort: ScreenerSort;
  setSort: (v: ScreenerSort) => void;
}) {
  return (
    <div
      data-testid="screener-filters"
      className="flex flex-wrap items-end gap-2 rounded-xl border border-border bg-surface p-3"
    >
      <Field label="Category" htmlFor="screener-category">
        <select
          id="screener-category"
          value={props.category}
          onChange={(e) => props.setCategory(e.target.value)}
          className="h-9 rounded-lg border border-border bg-bg px-2 font-mono text-[12px] font-semibold text-text outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-primary/25"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Min volume" htmlFor="screener-min-vol">
        <NumberInput
          id="screener-min-vol"
          value={props.minVolume}
          onChange={props.setMinVolume}
          placeholder="0"
          step={1000}
        />
      </Field>

      <Field label="Min |edge|" htmlFor="screener-min-edge">
        <NumberInput
          id="screener-min-edge"
          value={props.minEdge}
          onChange={props.setMinEdge}
          placeholder="0.00"
          step={0.005}
          min={0}
        />
      </Field>

      <Field label="Closing within (h)" htmlFor="screener-max-hours">
        <NumberInput
          id="screener-max-hours"
          value={props.maxHours}
          onChange={props.setMaxHours}
          placeholder="any"
          step={1}
          min={0}
        />
      </Field>

      <Field label="Sort" htmlFor="screener-sort">
        <select
          id="screener-sort"
          value={props.sort}
          onChange={(e) => props.setSort(e.target.value as ScreenerSort)}
          className="h-9 rounded-lg border border-border bg-bg px-2 font-mono text-[12px] font-semibold text-text outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-primary/25"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </Field>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <label htmlFor={htmlFor} className="flex flex-col gap-1">
      <span className="font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-muted-2">
        {label}
      </span>
      {children}
    </label>
  );
}

function NumberInput({
  id,
  value,
  onChange,
  placeholder,
  step,
  min,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  step?: number;
  min?: number;
}) {
  return (
    <input
      id={id}
      type="number"
      inputMode="decimal"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      step={step}
      min={min}
      className="h-9 w-[104px] rounded-lg border border-border bg-bg px-2 font-mono text-[12px] font-semibold text-text outline-none transition placeholder:text-muted-2 focus:border-primary/50 focus:ring-2 focus:ring-primary/25"
    />
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

const EDGE_W = "w-[88px]";

function ScreenerTable({
  items,
  sort,
  onSort,
}: {
  items: ScreenerItem[];
  sort: ScreenerSort;
  onSort: (s: ScreenerSort) => void;
}) {
  return (
    <table className="w-full border-collapse text-left">
      <caption className="sr-only">Screener results — paper markets ranked by edge</caption>
      <thead className="sticky top-0 z-10 bg-surface-2/95 backdrop-blur">
        <tr className="border-b border-border">
          <SortableTh
            label="Market"
            onClick={() => onSort("volume")}
            align="left"
            className="w-auto"
          />
          <th
            className="px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2"
            scope="col"
          >
            Category
          </th>
          <SortableTh label="Volume" onClick={() => onSort("volume")} align="right" />
          <th
            className="px-3 py-2 text-right font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2"
            scope="col"
          >
            Yes
          </th>
          <SortableTh label="24h" onClick={() => onSort("move")} align="right" />
          <SortableTh
            label="Edge"
            onClick={() => onSort("edge")}
            align="right"
            className={EDGE_W}
            active={sort === "edge"}
          />
          <SortableTh label="Close" onClick={() => onSort("closing")} align="right" />
          <th className="px-3 py-2" scope="col" aria-label="open market" />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <ScreenerRow key={item.slug} item={item} />
        ))}
      </tbody>
    </table>
  );
}

function SortableTh({
  label,
  onClick,
  align,
  className,
  active = false,
}: {
  label: string;
  onClick: () => void;
  align: "left" | "right";
  className?: string;
  active?: boolean;
}) {
  return (
    <th
      scope="col"
      className={cn(
        "px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em]",
        active ? "text-primary" : "text-muted-2",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
    >
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-1 transition hover:text-text"
      >
        {label}
        <span aria-hidden className="text-[8px]">
          ↕
        </span>
      </button>
    </th>
  );
}

function ScreenerRow({ item }: { item: ScreenerItem }) {
  const edgePositive = item.model_edge >= 0;
  return (
    <tr
      data-testid="screener-row"
      className="border-b border-border/60 transition hover:bg-surface-2/60"
    >
      <td className="px-3 py-2.5">
        <Link
          href={`/markets/${encodeURIComponent(item.slug)}`}
          className="group flex items-center gap-2"
          title={item.title}
        >
          <span
            aria-hidden
            className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary-dim/55 text-sm"
          >
            {item.icon}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-bold text-text transition group-hover:text-primary">
              {item.title}
            </span>
            <span className="block truncate font-mono text-[10px] text-muted-2">
              {item.slug}
            </span>
          </span>
        </Link>
      </td>
      <td className="px-3 py-2.5">
        <span className="rounded border border-border bg-bg/60 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.1em] text-muted-2">
          {item.category}
        </span>
      </td>
      <td className="px-3 py-2.5 text-right font-mono text-[12px] font-semibold text-text">
        {formatVolume(item.volume)}
      </td>
      <td className="px-3 py-2.5 text-right font-mono text-[12px] font-semibold text-text">
        {formatPrice(item.yes_price)}
      </td>
      <td
        className={cn(
          "px-3 py-2.5 text-right font-mono text-[12px] font-semibold",
          item.move_24h > 0
            ? "text-primary"
            : item.move_24h < 0
              ? "text-secondary"
              : "text-muted",
        )}
      >
        {formatPercent(item.move_24h)}
      </td>
      {/* Edge cell — mint positive, blue negative. NEVER red. */}
      <td
        data-testid="screener-edge"
        className={cn(
          "px-3 py-2.5 text-right font-mono text-[12px] font-black tabular-nums",
          edgePositive ? "text-primary" : "text-secondary",
        )}
      >
        {formatPercent(item.model_edge)}
      </td>
      <td className="px-3 py-2.5 text-right font-mono text-[12px] font-semibold text-muted">
        {formatHours(item.hours_to_close)}
      </td>
      <td className="px-3 py-2.5 text-right">
        <Link
          href={`/markets/${encodeURIComponent(item.slug)}`}
          className="inline-flex h-7 items-center rounded-lg px-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2 transition hover:text-primary"
        >
          Open →
        </Link>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Skeleton + empty state
// ---------------------------------------------------------------------------

function ScreenerSkeleton() {
  return (
    <div data-testid="screener-skeleton" aria-hidden="true">
      {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 border-b border-border/60 px-3 py-2.5"
        >
          <div className="t-skeleton h-7 w-7 rounded-lg" />
          <div className="t-skeleton h-3 w-40 rounded" />
          <div className="ml-auto t-skeleton h-3 w-16 rounded" />
          <div className="t-skeleton h-3 w-12 rounded" />
          <div className="t-skeleton h-3 w-12 rounded" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div
      data-testid="screener-empty"
      className="flex min-h-[36dvh] flex-col items-center justify-center px-6 py-12 text-center"
    >
      <span
        aria-hidden
        className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-dim/55 text-2xl"
      >
        ⌕
      </span>
      <h2 className="mt-4 text-lg font-bold text-text">
        {hasFilters ? "No markets match these filters" : "No markets to screen"}
      </h2>
      <p className="mt-1 max-w-sm text-sm text-muted">
        {hasFilters
          ? "Loosen the volume, edge, or closing-window filters and try again."
          : "Check back when the paper market feed publishes fresh rows."}
      </p>
    </div>
  );
}
