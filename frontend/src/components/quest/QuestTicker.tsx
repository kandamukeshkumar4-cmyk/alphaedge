"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchSignalsDashboard, type SignalFeedItem } from "@/lib/signals-dashboard-api";
import { fetchBriefs, type AnalystBrief } from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import { DEMO_BRIEFS, DEMO_SIGNALS } from "@/lib/demo-data";

type TickerItem = {
  id: string;
  kind: "signal" | "brief";
  label: string;
  text: string;
  href: string;
  edge?: boolean;
};

function toItems(signals: SignalFeedItem[], briefs: AnalystBrief[]): TickerItem[] {
  const out: TickerItem[] = [];
  for (const s of signals.slice(0, 8)) {
    out.push({
      id: `s-${s.id}`,
      kind: "signal",
      label: s.signal_type.replaceAll("_", " "),
      text: s.market_name,
      href: "/signals",
      edge: s.is_edge,
    });
  }
  for (const b of briefs.slice(0, 6)) {
    out.push({
      id: `b-${b.id}`,
      kind: "brief",
      label: b.kind === "digest" ? "daily digest" : "AI brief",
      text: b.headline || b.market_slug,
      href: `/research/brief/${b.market_slug}`,
    });
  }
  return out;
}

// Fixed bottom activity strip — live signals + fresh analyst briefs.
export function QuestTicker() {
  const [items, setItems] = useState<TickerItem[]>([]);
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    let dead = false;
    const load = async () => {
      const [dash, briefs] = await Promise.all([
        fetchSignalsDashboard().catch(() => null),
        fetchBriefs({ limit: 6 }).catch(() => null),
      ]);
      if (dead) return;
      const live = toItems(dash?.signals ?? [], briefs?.items ?? []);
      if (live.length > 0) {
        setItems(live);
        setDemo(false);
      } else {
        setItems(toItems(DEMO_SIGNALS, DEMO_BRIEFS));
        setDemo(true);
      }
    };
    void load();
    // Slow safety refresh — signals aren't on the WS feed, only briefs/alerts.
    const id = setInterval(() => void load(), 120_000);
    return () => {
      dead = true;
      clearInterval(id);
    };
  }, []);

  // Real-time: prepend fresh briefs the moment the analyst publishes them.
  useActivityFeed({
    onBrief: (frame) => {
      setDemo(false);
      setItems((prev) => {
        const live = prev.filter((it) => !it.id.includes("demo"));
        const item: TickerItem = {
          id: `ws-brief-${frame.ts ?? Date.now()}`,
          kind: "brief",
          label: "AI brief",
          text: frame.headline || frame.market_slug || "New brief",
          href: `/research/brief/${frame.market_slug ?? ""}`,
        };
        return [item, ...live].slice(0, 24);
      });
    },
  });

  if (items.length === 0) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-bg/95 backdrop-blur">
      <div className="no-scrollbar flex items-center gap-5 overflow-x-auto px-3 py-1">
        <span
          className={cn(
            "flex shrink-0 items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider",
            demo ? "text-secondary" : "text-muted-2",
          )}
          title={
            demo
              ? "Sample activity — start the backend for live signals and briefs"
              : "Live signals and briefs from the pipeline"
          }
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              demo ? "bg-secondary" : "bg-accent-bright",
            )}
          />
          {demo ? "Demo" : "Live"}
        </span>
        {items.map((it) => (
          <Link
            key={it.id}
            href={it.href}
            className="flex shrink-0 items-center gap-1.5 text-xs text-muted hover:text-text"
          >
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                it.kind === "brief"
                  ? "bg-accent-dim text-accent-bright"
                  : it.edge
                    ? "bg-primary-dim text-primary"
                    : "bg-surface-3 text-muted",
              )}
            >
              {it.label}
            </span>
            <span className="max-w-[260px] truncate">{it.text}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
