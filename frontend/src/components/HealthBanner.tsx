"use client";

import { useEffect, useRef, useState } from "react";

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

type DetailedHealth = {
  status: "ok" | "degraded" | "down";
};

type ProbeResult = "ok" | "degraded" | "down" | "fetch_fail";

const POLL_MS = 30_000;
// A single transient failure (HF Space 429 / cold start) must NOT flip the
// whole app to API-down. Require this many consecutive bad probes.
const FAILURES_BEFORE_DOWN = 2;
const RETRY_AFTER_FAILURE_MS = 5_000;

/** Honest API-down copy (loop67 L3) — never claims fabricated live data is real. */
export const API_DOWN_BANNER_MESSAGE =
  "Backend unreachable. Live paper-trading data is unavailable — this app will not invent markets, scores, or balances.";

export const API_DEGRADED_BANNER_MESSAGE =
  "AlphaEdge API is degraded. Some live features may be limited — no fabricated metrics are shown as healthy.";

async function probe(base: string): Promise<ProbeResult> {
  try {
    const response = await fetch(apiUrl("/api/v1/health/detailed", base), {
      cache: "no-store",
    });
    if (!response.ok) {
      // 429 = rate limited, not an outage — the API is alive.
      return "degraded";
    }
    const body = (await response.json()) as DetailedHealth;
    return body.status;
  } catch {
    return "fetch_fail";
  }
}

export function HealthBanner() {
  const [status, setStatus] = useState<ProbeResult | null>(null);
  const failStreak = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function loadHealth() {
      const base = await ensureApiBase();
      if (!hasLiveApi(base)) {
        if (!cancelled) setStatus("degraded");
        return;
      }

      const result = await probe(base);
      if (cancelled) return;

      if (result === "fetch_fail" || result === "down") {
        failStreak.current += 1;
        if (failStreak.current >= FAILURES_BEFORE_DOWN) {
          setStatus(result);
        } else {
          // First failure: stay quiet (or keep prior state) and re-probe soon.
          timer = setTimeout(() => void loadHealth(), RETRY_AFTER_FAILURE_MS);
          return;
        }
      } else {
        failStreak.current = 0;
        setStatus(result);
      }
      timer = setTimeout(() => void loadHealth(), POLL_MS);
    }

    void loadHealth();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (status === null || status === "ok") {
    return null;
  }

  // A dead/unreachable API (fetch_fail) is "unavailable", not "degraded".
  // Honest launch copy: backend unreachable — do not present fake live data.
  // Reached only after FAILURES_BEFORE_DOWN consecutive failed probes; poll
  // continues so recovery clears the banner automatically.
  const isDown = status === "down" || status === "fetch_fail";
  const message = isDown ? API_DOWN_BANNER_MESSAGE : API_DEGRADED_BANNER_MESSAGE;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="health-banner"
      data-status={isDown ? "down" : "degraded"}
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
