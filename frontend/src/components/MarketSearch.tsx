"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { MarketFilterParams } from "@/lib/alphaedge-api";

type SortOption = "volume" | "traders" | "newest";

const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "sports", label: "Sports" },
  { id: "politics", label: "Politics" },
  { id: "crypto", label: "Crypto" },
  { id: "culture", label: "Culture" },
  { id: "economics", label: "Economics" },
] as const;

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "volume", label: "Volume" },
  { value: "traders", label: "Traders" },
  { value: "newest", label: "Newest" },
];

type Props = {
  onChange: (params: MarketFilterParams) => void;
  loading?: boolean;
};

export function MarketSearch({ onChange, loading = false }: Props) {
  const [category, setCategory] = useState<string>("all");
  const [sort, setSort] = useState<SortOption>("volume");
  const [query, setQuery] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function fireChange(cat: string, s: SortOption, q: string) {
    onChange({
      category: cat === "all" ? undefined : cat,
      sort: s,
      q: q.trim() || undefined,
    });
  }

  function handleCategory(cat: string) {
    setCategory(cat);
    fireChange(cat, sort, query);
  }

  function handleSort(s: SortOption) {
    setSort(s);
    fireChange(category, s, query);
  }

  function handleQuery(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fireChange(category, sort, q);
    }, 300);
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div className="space-y-3">
      {/* Category tabs */}
      <div className="flex flex-wrap gap-1.5">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => handleCategory(cat.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-semibold transition",
              category === cat.id
                ? "border-primary bg-primary-dim text-primary"
                : "border-border bg-surface text-muted hover:border-border-light hover:text-text",
            )}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Search + sort row */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <span className="absolute inset-y-0 left-3 flex items-center text-muted pointer-events-none">
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="2" />
              <path d="M14 14l3.5 3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <input
            type="search"
            placeholder="Search markets…"
            value={query}
            onChange={handleQuery}
            className="w-full rounded-xl border border-border bg-surface py-2 pl-8 pr-3 text-sm text-text placeholder-muted outline-none transition focus:border-primary focus:ring-1 focus:ring-primary/40"
          />
        </div>

        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span className="hidden sm:inline">Sort:</span>
          <select
            value={sort}
            onChange={(e) => handleSort(e.target.value as SortOption)}
            className="rounded-xl border border-border bg-surface px-2 py-2 text-xs text-text outline-none transition focus:border-primary"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {loading && (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" />
        )}
      </div>
    </div>
  );
}
