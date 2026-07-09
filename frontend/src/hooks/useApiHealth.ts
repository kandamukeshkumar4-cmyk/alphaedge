"use client";

import { useEffect, useState } from "react";
import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

// "live"  = backend reachable and healthy → surfaces show real data
// "demo"  = backend unreachable / unconfigured → surfaces show sample data
// "checking" = first probe in flight
export type ApiHealth = "checking" | "live" | "demo";

// Pure classifier for the health probe, extracted so the live/demo decision is
// unit-testable without a React renderer (the test env is node, no jsdom).
// `res` is null when the fetch threw (backend unreachable).
// Empty apiBase is valid in browser prod (same-origin Vercel → HF rewrite).
export function classifyHealth(apiBase: string, res: { ok: boolean } | null): ApiHealth {
  if (!hasLiveApi(apiBase)) return "demo";
  if (res === null) return "demo";
  return res.ok ? "live" : "demo";
}

// Lightweight global health probe for the header LIVE/DEMO indicator. Hits the
// always-on `/health` endpoint (no auth, no data) so it stays cheap.
export function useApiHealth(pollMs = 30_000): ApiHealth {
  const [health, setHealth] = useState<ApiHealth>("checking");

  useEffect(() => {
    let dead = false;

    const check = async () => {
      const base = await ensureApiBase();
      if (!hasLiveApi(base)) {
        if (!dead) setHealth("demo");
        return;
      }
      try {
        const res = await fetch(apiUrl("/health", base), { cache: "no-store" });
        if (dead) return;
        setHealth(classifyHealth(base, res));
      } catch {
        if (!dead) setHealth(classifyHealth(base, null));
      }
    };

    void check();
    const id = setInterval(() => void check(), pollMs);
    return () => {
      dead = true;
      clearInterval(id);
    };
  }, [pollMs]);

  return health;
}
