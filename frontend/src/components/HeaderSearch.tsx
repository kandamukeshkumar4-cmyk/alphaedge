"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { searchUnified, type UnifiedSearchResult } from "@/lib/search-api";

const DEBOUNCE_MS = 250;
const RESULT_LIMIT = 8;

type SearchPhase = "idle" | "loading" | "results" | "empty" | "error";

function formatVolume(volume: number): string {
  if (volume >= 1_000_000) return `$${(volume / 1_000_000).toFixed(1)}M`;
  if (volume >= 1_000) return `$${(volume / 1_000).toFixed(1)}K`;
  return `$${Math.round(volume)}`;
}

export function HeaderSearch() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const requestSeq = useRef(0);
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<SearchPhase>("idle");
  const [results, setResults] = useState<UnifiedSearchResult[]>([]);
  const [openDropdown, setOpenDropdown] = useState(false);
  const [highlight, setHighlight] = useState(-1);

  // Debounced fetch; a sequence counter drops stale responses.
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setPhase("idle");
      setResults([]);
      return;
    }
    setPhase("loading");
    const seq = ++requestSeq.current;
    const timer = setTimeout(async () => {
      try {
        const found = await searchUnified(q, RESULT_LIMIT);
        if (seq !== requestSeq.current) return;
        setResults(found);
        setHighlight(-1);
        setPhase(found.length ? "results" : "empty");
      } catch {
        if (seq !== requestSeq.current) return;
        setResults([]);
        setPhase("error");
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  // Global "/" focuses the search box (unless typing elsewhere).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (target?.isContentEditable) return;
      event.preventDefault();
      inputRef.current?.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close when clicking outside.
  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpenDropdown(false);
      }
    }
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const goTo = useCallback(
    (result: UnifiedSearchResult) => {
      setOpenDropdown(false);
      setQuery("");
      router.push(`/markets/${result.slug}`);
    },
    [router],
  );

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpenDropdown(false);
      inputRef.current?.blur();
      return;
    }
    if (!results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => (h + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => (h <= 0 ? results.length - 1 : h - 1));
    } else if (event.key === "Enter" && highlight >= 0 && highlight < results.length) {
      event.preventDefault();
      goTo(results[highlight]);
    }
  }

  const showDropdown = openDropdown && query.trim().length > 0 && phase !== "idle";

  return (
    <div ref={rootRef} className="relative w-full">
      <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm text-muted transition focus-within:border-primary/45 focus-within:bg-surface-2">
        <SearchIcon />
        <input
          ref={inputRef}
          className="w-full bg-transparent text-sm font-medium text-text placeholder:text-muted-2 focus:outline-none"
          placeholder="Search markets…  ( / )"
          aria-label="Search markets"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls="header-search-results"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpenDropdown(true);
          }}
          onFocus={() => setOpenDropdown(true)}
          onKeyDown={onKeyDown}
        />
      </label>

      {showDropdown && (
        <div
          id="header-search-results"
          className="absolute inset-x-0 top-[calc(100%+6px)] z-50 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
        >
          {phase === "loading" && (
            <p className="px-3.5 py-3 text-sm text-muted">Searching…</p>
          )}
          {phase === "empty" && (
            <p className="px-3.5 py-3 text-sm text-muted">
              No markets match “{query.trim()}”.
            </p>
          )}
          {phase === "error" && (
            <p className="px-3.5 py-3 text-sm text-muted">
              Search is unavailable right now — try again shortly.
            </p>
          )}
          {phase === "results" && (
            <ul role="listbox" aria-label="Search results">
              {results.map((result, index) => (
                <li key={`${result.platform}-${result.slug}`} role="option" aria-selected={index === highlight}>
                  <button
                    type="button"
                    onClick={() => goTo(result)}
                    onMouseEnter={() => setHighlight(index)}
                    className={cn(
                      "flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left transition",
                      index === highlight ? "bg-surface-2" : "hover:bg-surface-2",
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-text">
                        {result.title}
                      </span>
                      <span className="mt-0.5 block font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
                        {result.platform} · {result.category}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      {result.yes_price !== null && (
                        <span className="block font-mono text-sm font-bold text-primary">
                          {Math.round(result.yes_price * 100)}%
                        </span>
                      )}
                      <span className="block font-mono text-[10px] text-muted-2">
                        {formatVolume(result.volume)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" strokeLinecap="round" />
    </svg>
  );
}
