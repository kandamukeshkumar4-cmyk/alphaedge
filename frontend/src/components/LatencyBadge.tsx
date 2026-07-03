"use client";

// Freshness badge from GET /markets/{slug}/latency. Degrades to "stale" quietly.
import { useEffect, useState } from "react";
import { fetchLatency, type LatencyBadge as Badge } from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";

const STYLE: Record<Badge["freshness"], string> = {
  live: "text-up border-up/40 bg-primary-dim",
  delayed: "text-gold border-gold/40 bg-secondary-dim",
  stale: "text-muted-2 border-border bg-surface-2",
};

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
