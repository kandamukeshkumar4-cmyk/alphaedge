"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchBriefs,
  fetchLatency,
  type AnalystBrief,
  type LatencyBadge,
} from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";

const FRESHNESS_TONE: Record<LatencyBadge["freshness"], string> = {
  live: "bg-primary-dim text-primary",
  delayed: "bg-secondary-dim text-secondary",
  stale: "bg-surface-3 text-muted",
};

// Market-detail analyst dock: latest AI brief for THIS market, its claim
// outcome, and the price-freshness badge — the T07/T08/T12 slice in situ.
export function QuestMarketRail({ slug }: { slug: string }) {
  const [brief, setBrief] = useState<AnalystBrief | null>(null);
  const [latency, setLatency] = useState<LatencyBadge | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    void Promise.all([
      fetchBriefs({ market: slug, limit: 1 }).catch(() => null),
      fetchLatency(slug).catch(() => null),
    ]).then(([page, lat]) => {
      if (dead) return;
      setBrief(page?.items?.[0] ?? null);
      setLatency(lat);
      setLoaded(true);
    });
    return () => {
      dead = true;
    };
  }, [slug]);

  if (!loaded) return null;

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">
          Analyst desk
        </h2>
        {latency && (
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
              FRESHNESS_TONE[latency.freshness],
            )}
            title={
              latency.age_seconds != null
                ? `Last tick ${Math.round(latency.age_seconds)}s ago`
                : "No ticks yet"
            }
          >
            {latency.freshness}
          </span>
        )}
      </div>

      {brief ? (
        <Link href={`/research/brief/${brief.market_slug}`} className="group mt-3 block">
          <p className="text-sm font-semibold text-text group-hover:text-accent-bright">
            {brief.headline}
          </p>
          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-muted">
            {brief.body_markdown.replace(/[#*_>`]/g, "").slice(0, 240)}
          </p>
          {brief.claim && (
            <p className="mt-2 font-mono text-[11px] text-muted-2">
              claim: <span className="text-text">{brief.claim.direction}</span> ·{" "}
              {brief.claim.horizon_minutes}m ·{" "}
              <span
                className={cn(
                  brief.claim.status === "correct" && "text-primary",
                  brief.claim.status === "incorrect" && "text-danger",
                )}
              >
                {brief.claim.status}
              </span>
            </p>
          )}
          <p className="mt-2 text-xs font-semibold text-accent-bright">
            Read full brief →
          </p>
        </Link>
      ) : (
        <p className="mt-3 text-xs leading-relaxed text-muted">
          No brief for this market yet. The analyst publishes automatically when
          price, whale, and news signals align.
        </p>
      )}

      <Link
        href="/track-record"
        className="mt-3 block rounded-lg border border-border px-3 py-2 text-center text-xs font-semibold text-muted transition hover:border-accent hover:text-accent-bright"
      >
        Analyst track record →
      </Link>
    </section>
  );
}
