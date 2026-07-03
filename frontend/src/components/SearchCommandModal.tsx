"use client";

/**
 * SearchCommandModal — cmd-k command palette for unified cross-platform market search (U01).
 *
 * Opens via:
 *   1. Keyboard shortcut: cmd-k (mac) / ctrl-k (windows/linux)
 *   2. Clicking the header search box
 *
 * Results are grouped by platform (Polymarket / Kalshi / AlphaEdge) and show:
 *   - Title, platform badge, category tag, live implied YES price
 *
 * Empty state: trending markets (all markets, no query).
 *
 * Platform badge styles reused from MarketCard.tsx.
 */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/alphaedge-api";
import { marketHref } from "@/lib/market-href";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SearchResult = {
  slug: string;
  title: string;
  platform: string;
  category: string;
  market_type: string;
  yes_price: number | null;
  volume: number;
  status: string;
};

// ---------------------------------------------------------------------------
// Platform badge styles — mirrors MarketCard.tsx PLATFORM_STYLES
// ---------------------------------------------------------------------------

const PLATFORM_BADGE: Record<string, string> = {
  Polymarket: "border-[#5B4FE8]/35 bg-[#5B4FE8]/15 text-[#B4ABFF]",
  Kalshi: "border-primary/35 bg-primary/15 text-primary",
  AlphaEdge: "border-accent/35 bg-accent/15 text-accent",
};

function platformBadgeClass(platform: string): string {
  return PLATFORM_BADGE[platform] ?? "border-border bg-surface-2 text-muted";
}

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function fetchSearchResults(q: string): Promise<SearchResult[]> {
  if (!API_BASE) return [];
  try {
    const url = new URL(`${API_BASE}/api/v1/search`);
    if (q.trim()) url.searchParams.set("q", q.trim());
    url.searchParams.set("limit", "20");
    const resp = await fetch(url.toString(), { cache: "no-store" });
    if (!resp.ok) return [];
    return (await resp.json()) as SearchResult[];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Group results by platform
// ---------------------------------------------------------------------------

function groupByPlatform(results: SearchResult[]): Record<string, SearchResult[]> {
  const groups: Record<string, SearchResult[]> = {};
  for (const r of results) {
    if (!groups[r.platform]) groups[r.platform] = [];
    groups[r.platform].push(r);
  }
  return groups;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PlatformSection({
  platform,
  markets,
  activeSlug,
  onSelect,
}: {
  platform: string;
  markets: SearchResult[];
  activeSlug: string | null;
  onSelect: (slug: string) => void;
}) {
  return (
    <div className="mb-2">
      <p className="mb-1 px-3 text-[10px] font-bold uppercase tracking-widest text-muted-2">
        {platform}
      </p>
      {markets.map((m) => (
        <button
          key={m.slug}
          type="button"
          onClick={() => onSelect(m.slug)}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition",
            activeSlug === m.slug
              ? "bg-surface-2"
              : "hover:bg-surface",
          )}
        >
          {/* Platform badge */}
          <span
            className={cn(
              "shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-[0.08em]",
              platformBadgeClass(m.platform),
            )}
          >
            {m.platform}
          </span>

          {/* Title */}
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-text">
            {m.title}
          </span>

          <div className="flex shrink-0 items-center gap-1.5">
            {/* Category tag */}
            <span className="hidden rounded border border-border bg-surface px-1.5 py-0.5 text-[9px] font-semibold text-muted sm:inline">
              {m.category}
            </span>

            {/* Market type tag */}
            <span className="hidden rounded border border-border bg-surface px-1.5 py-0.5 text-[9px] font-semibold text-muted lg:inline">
              {m.market_type}
            </span>

            {/* Implied YES price */}
            {m.yes_price != null ? (
              <span className="font-mono text-xs font-bold text-primary tabular-nums">
                {Math.round(m.yes_price * 100)}¢
              </span>
            ) : (
              <span className="font-mono text-xs text-muted">—</span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main modal component
// ---------------------------------------------------------------------------

type SearchCommandModalProps = {
  open: boolean;
  onClose: () => void;
};

export function SearchCommandModal({ open, onClose }: SearchCommandModalProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);

  // loadResults is a plain function (not memoized) — hoisted above useEffect
  // by declaring it outside via ref so the effect closure captures a stable ref.
  const loadResultsRef = useRef((q: string) => {
    setLoading(true);
    fetchSearchResults(q).then((data) => {
      setResults(data);
      setActiveSlug(data[0]?.slug ?? null);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  });

  // Focus input when modal opens; kick off trending load on empty query
  useEffect(() => {
    if (open) {
      setQuery("");
      setResults([]);
      setActiveSlug(null);
      loadResultsRef.current("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  function handleQuery(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => loadResultsRef.current(q), 200);
  }

  function navigateTo(slug: string) {
    onClose();
    router.push(marketHref(slug));
  }

  // Keyboard: Escape to close, arrow keys to navigate, Enter to select
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      onClose();
      return;
    }
    if (results.length === 0) return;
    const slugs = results.map((r) => r.slug);
    const currentIdx = activeSlug ? slugs.indexOf(activeSlug) : -1;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSlug(slugs[(currentIdx + 1) % slugs.length]);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSlug(slugs[(currentIdx - 1 + slugs.length) % slugs.length]);
    } else if (e.key === "Enter" && activeSlug) {
      e.preventDefault();
      navigateTo(activeSlug);
    }
  }

  if (!open) return null;

  const groups = groupByPlatform(results);
  const platforms = Object.keys(groups);

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center bg-bg/80 backdrop-blur-sm pt-[10vh]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal
      aria-label="Market search"
    >
      <div className="w-full max-w-xl rounded-2xl border border-border bg-bg shadow-2xl">
        {/* Search input */}
        <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
          <SearchIcon />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleQuery}
            onKeyDown={handleKeyDown}
            placeholder="Search markets across Polymarket &amp; Kalshi…"
            className="flex-1 bg-transparent text-sm text-text placeholder:text-muted-2 focus:outline-none"
            aria-label="Search markets"
          />
          {loading && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border border-border border-t-primary" />
          )}
          <kbd className="hidden rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted sm:inline">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[60vh] overflow-y-auto px-2 py-2">
          {!loading && results.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-2">
              {query ? `No markets found for "${query}"` : "No markets available"}
            </p>
          )}

          {platforms.length > 0 && (
            <div>
              {!query && (
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-2">
                  Trending markets
                </p>
              )}
              {platforms.map((platform) => (
                <PlatformSection
                  key={platform}
                  platform={platform}
                  markets={groups[platform]}
                  activeSlug={activeSlug}
                  onSelect={navigateTo}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[10px] text-muted-2">
          <span>
            <kbd className="rounded border border-border bg-surface px-1 py-0.5 font-mono text-[9px]">↑↓</kbd>{" "}
            navigate
          </span>
          <span>
            <kbd className="rounded border border-border bg-surface px-1 py-0.5 font-mono text-[9px]">↵</kbd>{" "}
            open
          </span>
          <span>Paper trading only</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hook — manage modal open state + cmd-k binding
// ---------------------------------------------------------------------------

export function useSearchCommandModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return { open, openModal: () => setOpen(true), closeModal: () => setOpen(false) };
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SearchIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="shrink-0 text-muted-2"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" strokeLinecap="round" />
    </svg>
  );
}
