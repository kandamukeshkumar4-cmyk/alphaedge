"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchSignalEvents, type SignalEventItem } from "@/lib/activity-api";
import { cn } from "@/lib/cn";
import { dedupeSignalEvents, relativeSignalAge } from "@/lib/signal-rail";

const EVENT_TONE: Record<string, string> = {
  price_jump: "bg-primary-dim text-primary",
  orderbook_flip: "bg-secondary-dim text-secondary",
  volume_surge: "bg-accent-dim text-accent-bright",
  whale_delta: "bg-accent-dim text-accent-bright",
  news_arrival: "bg-surface-3 text-text",
  alignment: "bg-primary-dim text-primary",
};

// Market-detail activity feed: the diff-engine / whale / news events for THIS
// market — the engine room behind the analyst brief. Hidden when empty.
export function QuestMarketActivity({ slug }: { slug: string }) {
  const [events, setEvents] = useState<SignalEventItem[]>([]);

  useEffect(() => {
    let dead = false;
    void fetchSignalEvents({ market: slug, limit: 16, dedupeWindowMinutes: 10 }).then((rows) => {
      if (!dead) setEvents(dedupeSignalEvents(rows).slice(0, 8));
    });
    return () => {
      dead = true;
    };
  }, [slug]);

  if (events.length === 0) return null;

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">
          Signal activity
        </h2>
        <Link
          href="/alerts"
          className="text-[11px] font-semibold text-accent-bright hover:underline"
        >
          All activity →
        </Link>
      </div>
      <ul className="mt-3 space-y-2">
        {events.map((e) => (
          <li key={e.id} className="flex items-center gap-2">
            <span
              className={cn(
                "shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                EVENT_TONE[e.signal_type] ?? "bg-surface-3 text-muted",
              )}
            >
              {e.signal_type.replaceAll("_", " ")}
            </span>
            <span className="min-w-0 flex-1 truncate text-[11px] uppercase text-muted-2">
              {e.platform}
            </span>
            <span className="shrink-0 text-[10px] text-muted-2">
              {relativeSignalAge(e.created_at)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
