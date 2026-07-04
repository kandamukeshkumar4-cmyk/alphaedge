"use client";

// Freshness badge from GET /markets/{slug}/latency. Degrades to "stale" quietly.
// U12: extended with SystemFreshnessBadge — a public data-freshness indicator
// that shows calibration drift alarm state without exposing internal metrics.
import { useEffect, useState } from "react";
import { fetchLatency, type LatencyBadge as Badge } from "@/lib/polyscout-api";
import { fetchDrift, type DriftResponse } from "@/lib/observability-api";
import { cn } from "@/lib/cn";

const STYLE: Record<Badge["freshness"], string> = {
  live: "text-up border-up/40 bg-primary-dim",
  delayed: "text-gold border-gold/40 bg-secondary-dim",
  stale: "text-muted-2 border-border bg-surface-2",
};

// ---------------------------------------------------------------------------
// U12 — System freshness badge (public, small footer widget)
// Shows: calibration status (ok / drift alarm) + data freshness.
// Honest unavailable state: renders "unavailable" when backend is unreachable.
// ---------------------------------------------------------------------------

type FreshnessState = "ok" | "alarm" | "unavailable";

const FRESHNESS_STYLE: Record<FreshnessState, string> = {
  ok: "text-up border-up/40 bg-primary-dim",
  alarm: "text-danger border-danger/40 bg-danger-dim",
  unavailable: "text-muted-2 border-border bg-surface-2",
};

const FRESHNESS_LABEL: Record<FreshnessState, string> = {
  ok: "data ok",
  alarm: "drift alarm",
  unavailable: "unavailable",
};

export function SystemFreshnessBadge() {
  const [state, setState] = useState<FreshnessState>("unavailable");
  const [drift, setDrift] = useState<DriftResponse | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      void fetchDrift().then((d) => {
        if (!alive) return;
        setDrift(d);
        if (d === null) {
          setState("unavailable");
        } else if (d.alarm) {
          setState("alarm");
        } else {
          setState("ok");
        }
      });
    };
    load();
    const t = setInterval(load, 60_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wide",
        FRESHNESS_STYLE[state],
      )}
      title={
        drift != null
          ? drift.insufficient_data
            ? "Calibration: insufficient data"
            : `Brier drift: ${drift.drift != null ? drift.drift.toFixed(4) : "n/a"}`
          : "System data unavailable"
      }
    >
      {state === "ok" && (
        <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-up" aria-hidden />
      )}
      {FRESHNESS_LABEL[state]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Original per-market LatencyBadge
// ---------------------------------------------------------------------------

export function LatencyBadge({ slug }: { slug: string }) {
  const [badge, setBadge] = useState<Badge | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => {
      void fetchLatency(slug).then((b) => {
        if (alive) setBadge(b);
      });
    };
    load();
    const t = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [slug]);

  if (!badge) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wide",
        STYLE[badge.freshness],
      )}
      title={
        badge.age_seconds != null
          ? `Last tick ${Math.round(badge.age_seconds)}s ago`
          : "No recent ticks"
      }
    >
      {badge.freshness === "live" && (
        <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-up" aria-hidden />
      )}
      {badge.freshness}
    </span>
  );
}
