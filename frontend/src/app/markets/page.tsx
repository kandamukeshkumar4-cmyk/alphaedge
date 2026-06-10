"use client";

import { useEffect, useState } from "react";

import { MarketCard, MarketCardSkeleton } from "@/components/MarketCard";
import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import {
  fetchMarkets,
  type Market,
  type MarketCategory,
} from "@/lib/markets-api";

type StatusFilter = "all" | "open" | "resolved";
type CategoryFilter = "all" | MarketCategory;

const CATEGORY_TABS: { label: string; value: CategoryFilter }[] = [
  { label: "All", value: "all" },
  { label: "NBA", value: "NBA" },
  { label: "FIFA WC2026", value: "FIFA WC2026" },
  { label: "Elections", value: "Elections" },
  { label: "Crypto", value: "Crypto" },
  { label: "Culture", value: "Culture" },
  { label: "Economics", value: "Economics" },
];

const STATUS_FILTERS: { label: string; value: StatusFilter }[] = [
  { label: "All", value: "all" },
  { label: "Open", value: "open" },
  { label: "Resolved", value: "resolved" },
];

function tabClass(active: boolean): string {
  return cn(
    "rounded-full border px-3.5 py-1.5 text-sm font-semibold transition",
    active
      ? "border-accent bg-accent/15 text-accent"
      : "border-border text-muted hover:border-border-light hover:text-text",
  );
}

export default function MarketsPage() {
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const apiConfigured = Boolean(API_BASE);

  useEffect(() => {
    if (!apiConfigured) {
      setLoading(false);
      setMarkets([]);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const apiFilter = filter === "all" ? undefined : filter;
        const apiCategory = category === "all" ? undefined : category;
        const next = await fetchMarkets(apiFilter, apiCategory);
        if (!cancelled) {
          setMarkets(next);
        }
      } catch (loadError) {
        if (!cancelled) {
          setMarkets([]);
          setError(
            loadError instanceof Error ? loadError.message : "Failed to load markets.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiConfigured, category, filter]);

  const emptyLabel =
    category === "all"
      ? filter === "all"
        ? ""
        : `${filter} `
      : filter === "all"
        ? `${category} `
        : `${category} ${filter} `;

  return (
    <main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-5">
      <div className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">
          Market discovery
        </p>
        <h1 className="mt-1 text-3xl font-black tracking-tight text-text">Markets</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Browse open and resolved prediction markets across Polymarket and Kalshi with
          implied YES pricing at a glance.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {CATEGORY_TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setCategory(item.value)}
            className={tabClass(category === item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setFilter(item.value)}
            className={tabClass(filter === item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {!apiConfigured ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          Set <code className="font-mono text-text">NEXT_PUBLIC_API_URL</code> to load live
          markets from the API.
        </div>
      ) : loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <MarketCardSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-10 text-center text-sm text-danger">
          {error}
        </div>
      ) : markets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          No {emptyLabel}markets found.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {markets.map((market) => (
            <MarketCard key={market.id} market={market} />
          ))}
        </div>
      )}
    </main>
  );
}
