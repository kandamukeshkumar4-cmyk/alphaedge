"use client";

/**
 * Loop V91 SU2 — command-palette market search.
 *
 * Opens as a centered modal (spring open; instant under reduced-motion),
 * debounces typing 200ms and aborts stale requests, then renders the frozen
 * V91 search contract rows from `searchMarkets` (live-first with a PAPER
 * mock fallback). Arrow keys navigate, Enter opens /markets/<slug>, ESC
 * closes. Astryx mint-on-charcoal tokens only — no danger-red anywhere.
 * Reserved body/footer heights keep the panel geometry stable (visreg-safe).
 */

import { motion, useReducedMotion, type Transition } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { searchMarkets, type SearchMarketItem } from "@/lib/search-api";
import { MagnifierIcon } from "./SearchIcons";
import { formatHoursToClose, formatSearchVolume, formatYesPct } from "./search-format";

const DEBOUNCE_MS = 200;
const RESULT_LIMIT = 20;

type Phase = "idle" | "loading" | "ready";

export function SearchPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [items, setItems] = useState<SearchMarketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [source, setSource] = useState<"live" | "mock">("mock");
  const [highlight, setHighlight] = useState(0);

  // Focus the input + lock page scroll while open; abort on unmount.
  useEffect(() => {
    inputRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
      abortRef.current?.abort();
    };
  }, []);

  // ESC closes from anywhere while the palette is open.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Debounced fetch; each keystroke aborts the previous in-flight request.
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      abortRef.current?.abort();
      setPhase("idle");
      setItems([]);
      setTotal(0);
      setHighlight(0);
      return;
    }
    setPhase("loading");
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const result = await searchMarkets(q, RESULT_LIMIT, controller.signal);
        if (controller.signal.aborted) return;
        setItems(result.items);
        setTotal(result.total);
        setSource(result.source);
        setHighlight(0);
        setPhase("ready");
      } catch {
        if (controller.signal.aborted) return; // superseded request — ignore
        setItems([]);
        setTotal(0);
        setSource("mock");
        setPhase("ready");
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  // Keep the highlighted row in view during keyboard navigation.
  useEffect(() => {
    rowRefs.current[highlight]?.scrollIntoView({ block: "nearest" });
  }, [highlight]);

  const openItem = useCallback(
    (item: SearchMarketItem) => {
      onClose();
      router.push(`/markets/${item.slug}`);
    },
    [onClose, router],
  );

  function onInputKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (items.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => (h + 1) % items.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => (h - 1 + items.length) % items.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const chosen = items[Math.min(Math.max(highlight, 0), items.length - 1)];
      if (chosen) openItem(chosen);
    }
  }

  // Minimal focus trap — Tab cycles within the panel.
  function onPanelKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab" || !panelRef.current) return;
    const focusable = panelRef.current.querySelectorAll<HTMLElement>(
      'input, button, [href], [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const panelSpring: Transition = reduceMotion
    ? { duration: 0 }
    : { type: "spring", stiffness: 420, damping: 34, mass: 0.9 };

  return (
    <motion.div
      className="fixed inset-0 z-[70] bg-bg/75 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.16 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <motion.div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search paper markets"
        data-testid="search-palette"
        onKeyDown={onPanelKeyDown}
        className="fixed left-1/2 top-[14vh] w-[min(600px,calc(100vw-32px))] overflow-hidden rounded-2xl border border-border-light bg-surface shadow-2xl shadow-black/50"
        initial={
          reduceMotion
            ? { opacity: 1, x: "-50%" }
            : { opacity: 0, x: "-50%", y: -14, scale: 0.97 }
        }
        animate={{ opacity: 1, x: "-50%", y: 0, scale: 1 }}
        exit={reduceMotion ? { opacity: 0, x: "-50%" } : { opacity: 0, x: "-50%", y: -8, scale: 0.98 }}
        transition={panelSpring}
      >
        {/* Query row */}
        <label className="flex h-14 items-center gap-3 border-b border-border px-4">
          <MagnifierIcon className="h-5 w-5 shrink-0 text-muted-2" />
          <input
            ref={inputRef}
            data-testid="search-input"
            role="combobox"
            aria-expanded={phase === "ready" && items.length > 0}
            aria-controls="search-palette-listbox"
            aria-label="Search paper markets"
            className="w-full bg-transparent text-[15px] font-medium text-text placeholder:text-muted-2 focus:outline-none"
            placeholder="Search NBA, elections, crypto…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
            spellCheck={false}
            autoComplete="off"
          />
          <kbd className="hidden shrink-0 rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-bold text-muted-2 sm:inline">
            ESC
          </kbd>
        </label>

        {/* Body — reserved height keeps panel geometry stable (visreg-safe). */}
        <div className="flex h-[340px] flex-col">
          {phase === "idle" && <EmptyState />}
          {phase === "loading" && <LoadingSkeleton />}
          {phase === "ready" && items.length > 0 && (
            <ul
              id="search-palette-listbox"
              role="listbox"
              aria-label="Search results"
              className="flex-1 overflow-y-auto py-1.5"
            >
              {items.map((item, index) => {
                const hours = formatHoursToClose(item.hours_to_close);
                return (
                  <li key={item.slug} role="option" aria-selected={index === highlight}>
                    <button
                      ref={(el) => {
                        rowRefs.current[index] = el;
                      }}
                      type="button"
                      data-testid="search-result-item"
                      onClick={() => openItem(item)}
                      onMouseEnter={() => setHighlight(index)}
                      className={cn(
                        "flex w-full items-center gap-3 px-3.5 py-2.5 text-left transition",
                        index === highlight
                          ? "bg-surface-2 ring-1 ring-inset ring-primary/40"
                          : "hover:bg-surface-2/60",
                      )}
                    >
                      <span
                        className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-border bg-surface-2 text-base"
                        aria-hidden="true"
                      >
                        {item.icon}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-text">
                          {item.title}
                        </span>
                        <span className="mt-1 flex items-center gap-2">
                          <span className="rounded border border-primary/25 bg-primary-dim/45 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-primary">
                            {item.category}
                          </span>
                          {hours ? (
                            <span className="font-mono text-[10px] text-muted-2">{hours}</span>
                          ) : null}
                        </span>
                      </span>
                      <span className="shrink-0 text-right">
                        <span className="block font-mono text-sm font-bold text-primary">
                          {formatYesPct(item.yes_price)}
                        </span>
                        <span className="block font-mono text-[10px] text-muted-2">
                          {formatSearchVolume(item.volume)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {phase === "ready" && items.length === 0 && <NoResults query={query.trim()} />}
        </div>

        {/* Footer — reserved height; paper disclaimer stays visible. */}
        <footer className="flex h-11 items-center justify-between gap-3 border-t border-border px-4">
          {source === "mock" && phase !== "idle" ? (
            <span
              data-testid="search-source-mock"
              className="rounded border border-primary/25 bg-primary-dim/45 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-primary"
            >
              Paper preview
            </span>
          ) : (
            <span aria-hidden="true" />
          )}
          <span className="font-mono text-[10px] text-muted-2">
            {phase === "ready" && items.length > 0
              ? `${total} paper ${total === 1 ? "market" : "markets"} · simulation only`
              : "Paper-trading simulation — no real funds"}
          </span>
        </footer>
      </motion.div>
    </motion.div>
  );
}

function EmptyState() {
  return (
    <div
      data-testid="search-empty-state"
      className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center"
    >
      <span className="grid h-12 w-12 place-items-center rounded-2xl border border-primary/25 bg-primary-dim/40 text-primary shadow-glow">
        <MagnifierIcon className="h-6 w-6" />
      </span>
      <div>
        <p className="text-sm font-bold text-text">Search paper markets</p>
        <p className="mt-1 text-xs text-muted-2">
          NBA, elections, crypto, economics — simulated odds only.
        </p>
      </div>
      <div className="flex items-center gap-3 font-mono text-[10px] text-muted-2">
        <span>
          <Kbd>↑</Kbd> <Kbd>↓</Kbd> navigate
        </span>
        <span>
          <Kbd>↵</Kbd> open
        </span>
        <span>
          <Kbd>esc</Kbd> close
        </span>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div
      data-testid="search-loading"
      aria-hidden="true"
      className="flex flex-1 flex-col gap-1.5 p-3"
    >
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex animate-pulse items-center gap-3 rounded-xl bg-surface-2/50 px-3 py-2.5 motion-reduce:animate-none"
        >
          <span className="h-9 w-9 shrink-0 rounded-lg bg-surface-3" />
          <span className="min-w-0 flex-1 space-y-2">
            <span className="block h-3 w-3/4 rounded bg-surface-3" />
            <span className="block h-2.5 w-1/3 rounded bg-surface-3" />
          </span>
          <span className="h-4 w-10 shrink-0 rounded bg-surface-3" />
        </div>
      ))}
    </div>
  );
}

function NoResults({ query }: { query: string }) {
  return (
    <div
      data-testid="search-no-results"
      className="flex flex-1 flex-col items-center justify-center gap-1.5 px-6 text-center"
    >
      <p className="text-sm font-semibold text-text">No markets match “{query}”.</p>
      <p className="text-xs text-muted-2">
        Try a team, topic, or category — e.g. “Lakers”, “Fed”, “Bitcoin”.
      </p>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-surface-2 px-1 py-0.5 font-mono text-[9px] font-bold text-muted">
      {children}
    </kbd>
  );
}
