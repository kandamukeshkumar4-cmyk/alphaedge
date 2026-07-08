"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";

export type AtlasMode = "idle" | "analyze" | "chat";

// Persisted so a user's explicit open/close choice survives navigation.
// Default is CLOSED: the panel must never auto-open and cover page content
// (it previously intercepted clicks on the signup form at small viewports).
const STORAGE_KEY = "alphaedge.atlas.open";

function readStoredOpen(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeStoredOpen(open: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  } catch {
    // Storage unavailable (private mode) — session-only state is fine.
  }
}

type AtlasPanelState = {
  open: boolean;
  mode: AtlasMode;
  marketSlug: string | null;
  marketTitle: string | null;
  seedPrompt: string | null;
  openPanel: (opts?: {
    mode?: AtlasMode;
    marketSlug?: string | null;
    marketTitle?: string | null;
    seedPrompt?: string | null;
  }) => void;
  closePanel: () => void;
  togglePanel: () => void;
  setMarket: (slug: string | null, title?: string | null) => void;
};

const AtlasPanelContext = createContext<AtlasPanelState | null>(null);

export function AtlasPanelProvider({ children }: { children: ReactNode }) {
  // Start closed on server and first client render (hydration-safe), then
  // restore the user's persisted preference.
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<AtlasMode>("idle");
  const [marketSlug, setMarketSlug] = useState<string | null>(null);
  const [marketTitle, setMarketTitle] = useState<string | null>(null);
  const [seedPrompt, setSeedPrompt] = useState<string | null>(null);
  const pathname = usePathname();
  const onAuthRoute = pathname?.startsWith("/auth") ?? false;

  useEffect(() => {
    if (!onAuthRoute && readStoredOpen()) {
      setOpen(true);
    }
  }, [onAuthRoute]);

  // Auth pages must never be covered by the panel.
  useEffect(() => {
    if (onAuthRoute) {
      setOpen(false);
    }
  }, [onAuthRoute]);

  const openPanel = useCallback(
    (opts?: {
      mode?: AtlasMode;
      marketSlug?: string | null;
      marketTitle?: string | null;
      seedPrompt?: string | null;
    }) => {
      setOpen(true);
      writeStoredOpen(true);
      if (opts?.mode) setMode(opts.mode);
      if (opts?.marketSlug !== undefined) setMarketSlug(opts.marketSlug);
      if (opts?.marketTitle !== undefined) setMarketTitle(opts.marketTitle ?? null);
      if (opts?.seedPrompt !== undefined) setSeedPrompt(opts.seedPrompt);
    },
    [],
  );

  const closePanel = useCallback(() => {
    setOpen(false);
    writeStoredOpen(false);
  }, []);
  const togglePanel = useCallback(() => {
    setOpen((v) => {
      writeStoredOpen(!v);
      return !v;
    });
  }, []);
  const setMarket = useCallback((slug: string | null, title?: string | null) => {
    setMarketSlug(slug);
    setMarketTitle(title ?? null);
  }, []);

  const value = useMemo(
    () => ({
      open: open && !onAuthRoute,
      mode,
      marketSlug,
      marketTitle,
      seedPrompt,
      openPanel,
      closePanel,
      togglePanel,
      setMarket,
    }),
    [
      open,
      onAuthRoute,
      mode,
      marketSlug,
      marketTitle,
      seedPrompt,
      openPanel,
      closePanel,
      togglePanel,
      setMarket,
    ],
  );

  return <AtlasPanelContext.Provider value={value}>{children}</AtlasPanelContext.Provider>;
}

export function useAtlasPanel(): AtlasPanelState {
  const ctx = useContext(AtlasPanelContext);
  if (!ctx) {
    throw new Error("useAtlasPanel must be used within AtlasPanelProvider");
  }
  return ctx;
}
