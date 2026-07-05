"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";

// "live"  = backend reachable and healthy → surfaces show real data
// "demo"  = backend unreachable / unconfigured → surfaces show sample data
// "checking" = first probe in flight
export type ApiHealth = "checking" | "live" | "demo";

// Lightweight global health probe for the header LIVE/DEMO indicator. Hits the
// always-on `/health` endpoint (no auth, no data) so it stays cheap.
export function useApiHealth(pollMs = 30_000): ApiHealth {
  const [health, setHealth] = useState<ApiHealth>("checking");

  useEffect(() => {
    if (!API_BASE) {
      setHealth("demo");
      return;
    }
    let dead = false;

    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (dead) return;
        setHealth(res.ok ? "live" : "demo");
      } catch {
        if (!dead) setHealth("demo");
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
