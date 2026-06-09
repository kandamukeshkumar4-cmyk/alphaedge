"use client";

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";

type DetailedHealth = {
  status: "ok" | "degraded" | "down";
};

export function HealthBanner() {
  const [status, setStatus] = useState<"ok" | "degraded" | "down" | "fetch_fail" | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      if (!API_BASE) {
        if (!cancelled) {
          setStatus("degraded");
        }
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/api/v1/health/detailed`, {
          cache: "no-store",
        });
        if (!response.ok) {
          if (!cancelled) {
            setStatus("degraded");
          }
          return;
        }
        const body = (await response.json()) as DetailedHealth;
        if (!cancelled) {
          setStatus(body.status);
        }
      } catch {
        if (!cancelled) {
          setStatus("fetch_fail");
        }
      }
    }

    void loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === null || status === "ok") {
    return null;
  }

  const isDown = status === "down";
  const message = isDown
    ? "AlphaEdge API is unavailable. Paper trading data may be stale."
    : "AlphaEdge API is degraded. Some features may be limited.";

  return (
    <div
      role="status"
      className={
        isDown
          ? "border-b border-danger/40 bg-danger-dim px-4 py-2 text-center text-sm font-semibold text-danger"
          : "border-b border-amber-500/40 bg-amber-500/10 px-4 py-2 text-center text-sm font-semibold text-amber-200"
      }
    >
      {message}
    </div>
  );
}
