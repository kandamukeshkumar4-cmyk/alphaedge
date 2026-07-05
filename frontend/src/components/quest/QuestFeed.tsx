"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchBriefs, type AnalystBrief } from "@/lib/polyscout-api";
import {
  fetchSignalsDashboard,
  type SignalFeedItem,
} from "@/lib/signals-dashboard-api";
import { cn } from "@/lib/cn";
import { DEMO_BRIEFS, DEMO_SIGNALS } from "@/lib/demo-data";
import { DemoChip } from "@/components/quest/DemoChip";

type FeedEntry =
  | { kind: "brief"; ts: number; brief: AnalystBrief }
  | { kind: "signal"; ts: number; signal: SignalFeedItem };

function buildFeed(briefs: AnalystBrief[], signals: SignalFeedItem[]): FeedEntry[] {
  const entries: FeedEntry[] = [
    ...briefs.map((b) => ({
      kind: "brief" as const,
      ts: Date.parse(b.created_at) || 0,
      brief: b,
    })),
    ...signals.map((s) => ({
      kind: "signal" as const,
      ts: Date.parse(s.created_at) || 0,
      signal: s,
    })),
  ];
  return entries.sort((a, b) => b.ts - a.ts).slice(0, 40);
}

function timeLabel(ts: number): string {
  if (!ts) return "";
  const mins = Math.max(0, Math.round((Date.now() - ts) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function claimTone(status: string | undefined): string {
  if (status === "correct") return "bg-primary-dim text-primary";
  if (status === "incorrect") return "bg-danger-dim text-danger";
  return "bg-surface-3 text-muted";
}

// Discover "Feed" tab — one reverse-chron timeline merging AI briefs (with
// claim outcomes) and edge signals. Everything links to its detail surface.
export function QuestFeed() {
  const [entries, setEntries] = useState<FeedEntry[] | null>(null);
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    let dead = false;
    void Promise.all([
      fetchBriefs({ limit: 20 }).catch(() => null),
      fetchSignalsDashboard().catch(() => null),
    ]).then(([briefs, dash]) => {
      if (dead) return;
      const live = buildFeed(briefs?.items ?? [], dash?.signals ?? []);
      if (live.length > 0) {
        setEntries(live);
      } else {
        setEntries(buildFeed(DEMO_BRIEFS, DEMO_SIGNALS));
        setDemo(true);
      }
    });
    return () => {
      dead = true;
    };
  }, []);

  if (entries === null) {
    return (
      <div className="mt-4 space-y-3">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="rounded-xl border border-border bg-surface p-4">
            <div className="skeleton h-4 w-2/3 rounded" />
            <div className="skeleton mt-2 h-3 w-1/3 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="mt-8 rounded-xl border border-border bg-surface p-8 text-center">
        <p className="text-sm font-semibold text-text">The feed is warming up</p>
        <p className="mx-auto mt-1 max-w-sm text-xs text-muted">
          Briefs and signals appear here as the pipeline detects moves. Start the
          backend workers, or run the analyst on any market.
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
      {demo && (
        <p className="flex items-center gap-2 rounded-lg border border-secondary/30 bg-secondary-dim px-4 py-2.5 text-xs text-secondary">
          <DemoChip />
          Sample feed — live briefs and signals replace this when the backend runs.
        </p>
      )}
      {entries.map((e) =>
        e.kind === "brief" ? (
          <Link
            key={`b-${e.brief.id}`}
            href={`/research/brief/${e.brief.market_slug}`}
            className="block rounded-xl border border-border bg-surface p-4 transition hover:border-border-light"
          >
            <div className="flex items-center gap-2">
              <span className="rounded bg-accent-dim px-1.5 py-0.5 text-[9px] font-bold uppercase text-accent-bright">
                {e.brief.kind === "digest" ? "Daily digest" : "AI brief"}
              </span>
              {e.brief.claim && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                    claimTone(e.brief.claim.status),
                  )}
                >
                  claim: {e.brief.claim.status}
                </span>
              )}
              <span className="ml-auto text-[10px] text-muted-2">{timeLabel(e.ts)}</span>
            </div>
            <p className="mt-2 text-sm font-semibold text-text">{e.brief.headline}</p>
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">
              {e.brief.body_markdown.replace(/[#*_>`]/g, "").slice(0, 220)}
            </p>
            {e.brief.claim && (
              <p className="mt-2 font-mono text-[11px] text-muted-2">
                {e.brief.claim.direction} · {e.brief.claim.horizon_minutes}m horizon ·{" "}
                {Math.round(e.brief.claim.confidence * 100)}% conf
              </p>
            )}
          </Link>
        ) : (
          <Link
            key={`s-${e.signal.id}`}
            href="/signals"
            className="block rounded-xl border border-border bg-surface p-4 transition hover:border-border-light"
          >
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                  e.signal.is_edge ? "bg-primary-dim text-primary" : "bg-surface-3 text-muted",
                )}
              >
                {e.signal.signal_type.replaceAll("_", " ")}
              </span>
              <span className="text-[10px] uppercase text-muted-2">{e.signal.platform}</span>
              <span className="ml-auto text-[10px] text-muted-2">{timeLabel(e.ts)}</span>
            </div>
            <p className="mt-2 text-sm font-semibold text-text">{e.signal.market_name}</p>
            {e.signal.implied_edge != null && (
              <p className="mt-1 font-mono text-[11px] text-accent-bright">
                implied edge {(e.signal.implied_edge * 100).toFixed(1)}%
                {e.signal.provisional ? " · provisional" : ""}
              </p>
            )}
          </Link>
        ),
      )}
    </div>
  );
}
