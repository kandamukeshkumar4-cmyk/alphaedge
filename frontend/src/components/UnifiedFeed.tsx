"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchFeed, subscribeFeedWS, type FeedItem, type FeedItemType } from "@/lib/feed-api";

// ---------------------------------------------------------------------------
// Type icon
// ---------------------------------------------------------------------------

function TypeIcon({ type }: { type: FeedItemType }) {
  switch (type) {
    case "alignment":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z" strokeLinejoin="round" />
          <path d="M2 17l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "whale_delta":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 19a9 9 0 0 1 9-9 9 9 0 0 1 6.2 2.5" strokeLinecap="round" />
          <path d="M14 10l4-4-4-4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M3 7v7h7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "news_arrival":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 4h16v12H4z" strokeLinejoin="round" />
          <path d="M8 8h8M8 12h5" strokeLinecap="round" />
          <path d="M4 20h16" strokeLinecap="round" />
        </svg>
      );
    case "instability_shift":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "brief":
    case "digest":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" strokeLinecap="round" />
          <line x1="16" y1="17" x2="8" y2="17" strokeLinecap="round" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      );
    case "claim_graded":
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="20 6 9 17 4 12" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    default:
      return (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" strokeLinecap="round" />
          <line x1="12" y1="16" x2="12.01" y2="16" strokeLinecap="round" />
        </svg>
      );
  }
}

// ---------------------------------------------------------------------------
// Type badge colour
// ---------------------------------------------------------------------------

function typeBadgeClass(type: FeedItemType): string {
  switch (type) {
    case "alignment":
      return "bg-primary-dim text-primary";
    case "whale_delta":
      return "bg-secondary-dim text-secondary";
    case "news_arrival":
      return "bg-accent-dim text-accent-bright";
    case "instability_shift":
      return "bg-danger-dim text-danger";
    case "brief":
    case "digest":
      return "bg-surface-3 text-muted";
    case "claim_graded":
      return "bg-primary-dim text-primary";
    default:
      return "bg-surface-3 text-muted";
  }
}

function typeLabel(type: FeedItemType): string {
  const labels: Record<FeedItemType, string> = {
    alignment: "Alignment",
    whale_delta: "Whale",
    news_arrival: "News",
    instability_shift: "Instability",
    brief: "AI Brief",
    digest: "Daily Digest",
    claim_graded: "Graded",
    signal: "Signal",
  };
  return labels[type] ?? type;
}

// ---------------------------------------------------------------------------
// Time helper
// ---------------------------------------------------------------------------

function timeLabel(ts: string): string {
  const ms = Date.parse(ts);
  if (!ms) return "";
  const mins = Math.max(0, Math.round((Date.now() - ms) / 60_000));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Single feed item card
// ---------------------------------------------------------------------------

function FeedCard({ item }: { item: FeedItem }) {
  const [expanded, setExpanded] = useState(false);
  const marketHref = `/markets/${item.market_slug}`;
  const hasDetail = Object.keys(item.payload).length > 0;

  return (
    <div className="rounded-xl border border-border bg-surface transition hover:border-border-light">
      <div className="flex items-start gap-3 p-4">
        {/* Icon */}
        <span className={cn("mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg", typeBadgeClass(item.item_type))}>
          <TypeIcon type={item.item_type} />
        </span>

        {/* Body */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={cn("rounded px-1.5 py-0.5 text-[9px] font-bold uppercase", typeBadgeClass(item.item_type))}>
              {typeLabel(item.item_type)}
            </span>
            {item.platform && (
              <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[9px] font-bold uppercase text-muted">
                {item.platform}
              </span>
            )}
            {item.confidence != null && (
              <span className="font-mono text-[10px] text-accent-bright">
                {Math.round(item.confidence * 100)}% conf
              </span>
            )}
            {item.target && (
              <span className="font-mono text-[10px] text-muted-2">{item.target}</span>
            )}
            <span className="ml-auto text-[10px] text-muted-2">{timeLabel(item.timestamp)}</span>
          </div>

          <p className="mt-1.5 text-sm font-semibold text-text">{item.summary}</p>

          {item.market_title ? (
            <Link
              href={marketHref}
              className="mt-1 inline-block text-xs text-accent-bright hover:underline"
            >
              {item.market_title}
            </Link>
          ) : (
            <Link
              href={marketHref}
              className="mt-1 inline-block font-mono text-[11px] text-muted-2 hover:text-text"
            >
              {item.market_slug}
            </Link>
          )}

          {hasDetail && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-2 text-[11px] text-muted hover:text-text"
            >
              {expanded ? "▲ Hide detail" : "▼ Show detail"}
            </button>
          )}

          {expanded && hasDetail && (
            <pre className="mt-2 overflow-x-auto rounded-lg border border-border bg-bg p-2 font-mono text-[10px] text-muted">
              {JSON.stringify(item.payload, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface UnifiedFeedProps {
  activeType: string;
  activePlatform: string;
}

export function UnifiedFeed({ activeType, activePlatform }: UnifiedFeedProps) {
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [liveCount, setLiveCount] = useState(0);
  const seenIds = useRef(new Set<string>());

  // Initial load from REST
  useEffect(() => {
    let dead = false;
    seenIds.current.clear();

    const params: Record<string, string> = { limit: "40", offset: "0" };
    if (activeType) params.item_type = activeType;
    if (activePlatform) params.platform = activePlatform;

    void fetchFeed(params).then((page) => {
      if (dead) return;
      page.items.forEach((i) => seenIds.current.add(i.id));
      setItems(page.items);
      setTotal(page.total);
    });

    return () => {
      dead = true;
    };
  }, [activeType, activePlatform]);

  // Live WS updates
  useEffect(() => {
    const unsub = subscribeFeedWS((newItem) => {
      // Apply active filters client-side
      if (activeType && newItem.item_type !== activeType) return;
      if (activePlatform && newItem.platform !== activePlatform) return;
      if (seenIds.current.has(newItem.id)) return;

      seenIds.current.add(newItem.id);
      setItems((prev) => (prev ? [newItem, ...prev].slice(0, 100) : [newItem]));
      setLiveCount((n) => n + 1);
    });
    return unsub;
  }, [activeType, activePlatform]);

  if (items === null) {
    return (
      <div className="mt-4 space-y-3">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="rounded-xl border border-border bg-surface p-4">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 animate-pulse rounded-lg bg-surface-3" />
              <div className="flex-1">
                <div className="h-3 w-24 animate-pulse rounded bg-surface-3" />
                <div className="mt-2 h-4 w-2/3 animate-pulse rounded bg-surface-3" />
                <div className="mt-1 h-3 w-1/3 animate-pulse rounded bg-surface-3" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="mt-8 rounded-xl border border-border bg-surface p-8 text-center">
        <p className="text-sm font-semibold text-text">No feed items yet</p>
        <p className="mx-auto mt-1 max-w-sm text-xs text-muted">
          {activeType
            ? `No "${activeType}" events yet. Try "All" or start the backend workers.`
            : "Signal events, briefs, and graded claims appear here as the pipeline runs."}
        </p>
        <Link
          href="/markets"
          className="mt-4 inline-block rounded-lg bg-accent-bright px-4 py-2 text-sm font-semibold text-bg"
        >
          Browse markets
        </Link>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      {liveCount > 0 && (
        <p className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary-dim px-4 py-2 text-xs text-primary">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
          {liveCount} new event{liveCount !== 1 ? "s" : ""} received live
        </p>
      )}
      {items.map((item) => (
        <FeedCard key={item.id} item={item} />
      ))}
      {total > items.length && (
        <p className="text-center text-xs text-muted-2">
          Showing {items.length} of {total} — use the offset param to paginate
        </p>
      )}
    </div>
  );
}
