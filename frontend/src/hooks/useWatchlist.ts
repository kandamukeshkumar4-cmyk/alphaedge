"use client";

import { useCallback, useEffect, useState } from "react";

import { ACCESS_TOKEN_KEY } from "@/lib/portfolio-api";
import {
  addWatchlist,
  fetchWatchlist,
  removeWatchlist,
  toggleWatchlistSlug,
} from "@/lib/watchlist-api";

// Same-tab sync so every star + the /watchlist page share one source of truth
// without re-fetching (mirrors the auth-changed pattern).
const WATCHLIST_CHANGED_EVENT = "alphaedge:watchlist-changed";

let sharedSlugs: string[] = [];

function broadcast(slugs: string[]) {
  sharedSlugs = slugs;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(WATCHLIST_CHANGED_EVENT, { detail: slugs }));
  }
}

/**
 * W01 — shared watchlist state. Loads the server set once (per token), keeps an
 * in-memory slug list, and applies optimistic add/remove (reverting on a failed
 * mutation). `toggle` returns "anon" when there is no session so the caller can
 * route to sign-in — watchlist bookmarks require a JWT (they are NOT orders).
 */
export function useWatchlist() {
  const [slugs, setSlugs] = useState<string[]>(sharedSlugs);
  const [token, setToken] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
    setToken(stored);
    let dead = false;
    void fetchWatchlist(stored).then((entries) => {
      if (dead) return;
      const next = entries.map((e) => e.slug);
      broadcast(next);
      setSlugs(next);
      setLoaded(true);
    });

    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<string[]>).detail;
      if (Array.isArray(detail)) setSlugs(detail);
    };
    window.addEventListener(WATCHLIST_CHANGED_EVENT, onChange);
    return () => {
      dead = true;
      window.removeEventListener(WATCHLIST_CHANGED_EVENT, onChange);
    };
  }, []);

  const isWatched = useCallback((slug: string) => slugs.includes(slug), [slugs]);

  const toggle = useCallback(
    async (slug: string): Promise<"anon" | "ok"> => {
      const currentToken = localStorage.getItem(ACCESS_TOKEN_KEY);
      if (!currentToken) return "anon";

      const before = sharedSlugs;
      const { next, action } = toggleWatchlistSlug(before, slug);
      broadcast(next);
      setSlugs(next);

      const ok =
        action === "add"
          ? await addWatchlist(currentToken, slug)
          : await removeWatchlist(currentToken, slug);
      if (!ok) {
        // Revert the optimistic update on failure.
        broadcast(before);
        setSlugs(before);
      }
      return "ok";
    },
    [],
  );

  return { slugs, isWatched, toggle, token, loaded, hasSession: !!token };
}
