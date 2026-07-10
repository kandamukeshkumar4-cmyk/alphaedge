"use client";

// X03 — recent alerts for the caller's tracked markets (backend K03,
// GET /api/v1/watchlist/alerts). Authed: the feed is pre-filtered to the
// caller's watchlist slugs server-side, so one call. Rendered with the shared
// SignalEvidence block. Honest empty when nothing has fired. Notify/read only —
// alerts never place trades. Fetch-once per token (no poll loop).
import Link from "next/link";
import { useEffect, useState } from "react";

import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { cn } from "@/lib/cn";
import {
  buildAlertGroups,
  fetchWatchlistAlerts,
  type AlertEventItem,
} from "@/lib/alerts-api";
import { marketHref } from "@/lib/market-href";

export function WatchlistAlerts({ token }: { token: string | null }) {
  const [items, setItems] = useState<AlertEventItem[] | null>(null);

  useEffect(() => {
    if (!token) {
      setItems([]);
      return;
    }
    let dead = false;
    const ctrl = new AbortController();
    setItems(null);
    void fetchWatchlistAlerts(token, { limit: 40 }).then((data) => {
      if (!dead) setItems(data);
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [token]);

  if (!token) return null;

  const groups = items ? buildAlertGroups(items) : [];

  return (
    <section aria-label="Recent alerts on your watchlist" className="mt-8">
      <h2 className="mb-3 text-sm font-black tracking-tight text-text">Recent alerts on your watchlist</h2>

      {items === null ? (
        <div className="space-y-3" aria-hidden>
          {[0, 1].map((i) => (
            <div key={i} className="rounded-xl border border-border bg-surface p-4">
              <div className="skeleton h-4 w-1/2 rounded" />
              <div className="skeleton mt-3 h-12 w-full rounded" />
            </div>
          ))}
        </div>
      ) : groups.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-surface p-6 text-center">
          <p className="text-sm font-semibold text-text">No alerts on your tracked markets yet</p>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">
            When the pipeline flags a model mispricing, unusual flow, or screener hit on a market you
            track, it shows here.{" "}
            <Link href="/alerts" className="font-semibold text-accent hover:underline">
              See all alerts →
            </Link>
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {groups.map((group) => (
            <li key={group.slug} className="rounded-xl border border-border bg-surface p-4">
              <div className="flex items-center gap-2">
                <Link
                  href={marketHref(group.slug)}
                  className="min-w-0 flex-1 truncate font-mono text-sm font-semibold text-text hover:text-accent-bright"
                >
                  {group.slug}
                </Link>
                <span className="shrink-0 rounded bg-surface-3 px-1.5 py-0.5 text-[10px] font-bold text-muted">
                  {group.count} alert{group.count === 1 ? "" : "s"}
                </span>
                <span className="shrink-0 text-[10px] text-muted-2">{group.latestLabel}</span>
              </div>
              <ul className="mt-3 space-y-3">
                {group.rows.map((row) => (
                  <li key={row.id} className="border-t border-border/60 pt-3 first:border-0 first:pt-0">
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className={cn("font-semibold text-text")}>{row.typeLabel}</span>
                      <span className="ml-auto text-muted-2">{row.timeLabel}</span>
                    </div>
                    {row.evidence ? <SignalEvidenceBlock evidence={row.evidence} /> : null}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
