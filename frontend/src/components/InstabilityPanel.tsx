"use client";

// Instability index panel (E07 / T13) — per-region 0-100 rolling scores from
// the news event taxonomy. PROVISIONAL: the scoring model has not been
// validated against an election dataset yet, and it never feeds forecasts for
// NBA/Sports. Reads the instability signal_events written by the backend.
import { useEffect, useState } from "react";
import { fetchSignalEvents } from "@/lib/activity-api";
import { cn } from "@/lib/cn";

type RegionScore = {
  region: string;
  score: number;
  prev: number;
  at: string;
};

function num(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0; // guard non-numeric payload → never NaN in UI
}

function latestPerRegion(
  events: Array<{ payload: Record<string, unknown>; created_at: string }>,
): RegionScore[] {
  const seen = new Map<string, RegionScore>();
  for (const e of events) {
    const region = String(e.payload.region ?? "");
    if (!region || seen.has(region)) continue; // events arrive newest-first
    seen.set(region, {
      region,
      score: num(e.payload.score),
      prev: num(e.payload.prev),
      at: e.created_at,
    });
  }
  return [...seen.values()].sort((a, b) => b.score - a.score);
}

export function InstabilityPanel() {
  const [regions, setRegions] = useState<RegionScore[] | null>(null);

  useEffect(() => {
    let dead = false;
    fetchSignalEvents({ signalType: "instability", limit: 100 })
      .then((events) => {
        if (!dead) setRegions(latestPerRegion(events));
      })
      .catch(() => {
        if (!dead) setRegions([]);
      });
    return () => {
      dead = true;
    };
  }, []);

  if (regions === null) return null;

  return (
    <section className="mb-6 rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">
          Instability index
        </h2>
        <span className="rounded bg-secondary-dim px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-secondary">
          provisional
        </span>
      </div>
      <p className="mt-1 text-xs text-muted">
        Per-region 0–100 score from severity-weighted news events (15-category
        taxonomy, decay-weighted). Research context only — unvalidated model, never
        applied to sports forecasts.
      </p>

      {regions.length === 0 ? (
        <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2.5 text-xs text-muted">
          No region scores yet. Scores accumulate as the news worker tags events
          (requires the backend workers running with news sources configured).
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          {regions.slice(0, 8).map((r) => {
            const rising = r.score > r.prev;
            const hot = r.score >= 50;
            return (
              <div key={r.region} className="flex items-center gap-2">
                <span className="w-28 truncate text-xs capitalize text-text">{r.region}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
                  <div
                    className={cn("h-full rounded-full", hot ? "bg-danger" : "bg-secondary")}
                    style={{ width: `${Math.min(100, Math.max(2, r.score))}%` }}
                  />
                </div>
                <span className="w-16 text-right font-mono text-[11px] tabular-nums text-text">
                  {r.score.toFixed(0)}
                  <span className={cn("ml-1", rising ? "text-danger" : "text-muted-2")}>
                    {rising ? "▲" : "▬"}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
