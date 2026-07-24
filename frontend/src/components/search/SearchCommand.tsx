"use client";

/**
 * Loop V91 SU2 — header search trigger + command-palette host.
 *
 * A magnifier button with a platform-aware Cmd/Ctrl-K hint opens the
 * SearchPalette modal; the same hotkey toggles it from anywhere on the
 * page. SiteHeader mounts this component and nothing else of the palette.
 */

import { AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { MagnifierIcon } from "./SearchIcons";
import { SearchPalette } from "./SearchPalette";

function platformHint(): string {
  if (typeof navigator === "undefined") return "Ctrl K";
  return /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent) ? "⌘K" : "Ctrl K";
}

export function SearchCommand() {
  const [open, setOpen] = useState(false);
  const [hint, setHint] = useState("");
  const openedOnce = useRef(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Hydration-safe: the kbd hint is resolved client-side after mount.
  useEffect(() => {
    setHint(platformHint());
  }, []);

  // Cmd/Ctrl-K toggles the palette globally (browser address-bar shortcut wins
  // nowhere we care about — we preventDefault so the palette gets the key).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Return focus to the trigger when the palette closes (not on first mount).
  useEffect(() => {
    if (open) {
      openedOnce.current = true;
      return;
    }
    if (openedOnce.current) triggerRef.current?.focus();
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        data-testid="search-trigger"
        aria-label="Search markets"
        aria-keyshortcuts="Control+K"
        title="Search markets"
        onClick={() => setOpen(true)}
        className="flex h-9 shrink-0 items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-muted transition hover:border-border-light hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        <MagnifierIcon className="h-4 w-4" />
        {hint ? (
          <kbd className="hidden rounded border border-border-light bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-bold text-muted-2 sm:inline">
            {hint}
          </kbd>
        ) : null}
      </button>
      <AnimatePresence>
        {open ? <SearchPalette onClose={() => setOpen(false)} /> : null}
      </AnimatePresence>
    </>
  );
}
