"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchBriefs,
  fetchTrackRecord,
  type AnalystBrief,
  type TrackRecordRow,
} from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";
import { DEMO_BRIEFS, DEMO_TRACK_RECORD } from "@/lib/demo-data";
import { DemoChip } from "@/components/quest/DemoChip";

// Right-side AI analyst dock — surfaces the T07 analyst + T08 track record.
export function QuestAgentPanel() {
  const [briefs, setBriefs] = useState<AnalystBrief[]>([]);
  const [record, setRecord] = useState<TrackRecordRow | null>(null);
  const [demo, setDemo] = useState(false);
  const [recordDemo, setRecordDemo] = useState(false);

  useEffect(() => {
    fetchBriefs({ limit: 4 })
      .then((page) => {
        const items = page?.items ?? [];
        if (items.length > 0) setBriefs(items);
        else {
          setBriefs(DEMO_BRIEFS);
          setDemo(true);
        }
      })
      .catch(() => {
        setBriefs(DEMO_BRIEFS);
        setDemo(true);
      });
    fetchTrackRecord()
      .then((rows) => {
        const row = rows.find((r) => r.window_days === 30) ?? rows[0] ?? null;
        if (row) {
          setRecord(row);
        } else {
          setRecord(DEMO_TRACK_RECORD[0]);
          setRecordDemo(true);
        }
      })
      .catch(() => {
        setRecord(DEMO_TRACK_RECORD[0]);
        setRecordDemo(true);
      });
  }, []);

  return (
    <aside className="no-scrollbar flex w-full flex-col gap-2 xl:sticky xl:top-12 xl:max-h-[calc(100vh-3.5rem)] xl:w-[240px] xl:shrink-0 xl:self-start xl:overflow-y-auto">
      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-bright opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent-bright" />
          </span>
          <h2 className="text-sm font-semibold text-text">AlphaEdge Analyst</h2>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted">
          The in-house AI analyst watches every price jump, whale move and news
          arrival. When ≥3 signals align it publishes a cited brief with a
          falsifiable claim — then gets graded on it.
        </p>
        {recordDemo ? (
          // No graded claims yet — show the honest reality, not sample numbers.
          <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2.5 text-xs text-muted">
            No graded claims yet. Accuracy and Brier appear here once the analyst&rsquo;s
            claims reach their horizon and get scored.
          </p>
        ) : (
          record && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-surface-2 p-2.5">
                <p className="text-[10px] uppercase tracking-wide text-muted-2">Accuracy 30d</p>
                <p className="font-mono text-lg font-semibold text-accent-bright">
                  {record.accuracy != null ? `${Math.round(record.accuracy * 100)}%` : "—"}
                </p>
              </div>
              <div className="rounded-lg bg-surface-2 p-2.5">
                <p className="text-[10px] uppercase tracking-wide text-muted-2">Brier</p>
                <p className="font-mono text-lg font-semibold text-text">
                  {record.brier != null ? record.brier.toFixed(3) : "—"}
                </p>
              </div>
            </div>
          )
        )}
        <Link
          href="/track-record"
          className="mt-3 block rounded-lg border border-border px-3 py-2 text-center text-xs font-semibold text-muted transition hover:border-accent hover:text-accent-bright"
        >
          Full public track record →
        </Link>
      </section>

      <section className="rounded-xl border border-border bg-surface p-3">
        <p className="px-1 text-[10px] font-bold uppercase tracking-wide text-muted-2">
          Quick actions
        </p>
        <div className="mt-2 space-y-1.5">
          <Link
            href="/signals"
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-muted transition hover:border-accent hover:text-text"
          >
            <span className="text-accent-bright">◎</span> Find edge signals
          </Link>
          <Link
            href="/portfolio"
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-muted transition hover:border-accent hover:text-text"
          >
            <span className="text-accent-bright">▤</span> Check your positions
          </Link>
          <Link
            href="/alerts"
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-muted transition hover:border-accent hover:text-text"
          >
            <span className="text-accent-bright">⚡</span> Watch the engine room
          </Link>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface">
        <Link
          href="/research"
          className="flex items-center justify-between px-4 py-3 text-sm font-semibold text-text hover:text-accent-bright"
        >
          <span className="flex items-center gap-2">
            Latest AI briefs
            {demo && <DemoChip />}
          </span>
          <span className="text-muted-2">›</span>
        </Link>
        <div className="px-2 pb-2">
          {briefs.length === 0 ? (
            <p className="px-2 pb-2 text-xs text-muted-2">
              Briefs publish automatically when signals align.
            </p>
          ) : (
            briefs.map((b) => (
              <Link
                key={b.id}
                href={`/research/brief/${b.market_slug}`}
                className="block rounded-lg px-2 py-2 hover:bg-surface-2"
              >
                <p className="truncate text-xs font-medium text-text">
                  {b.headline || b.market_slug}
                </p>
                <p
                  className={cn(
                    "mt-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    b.kind === "digest" ? "text-secondary" : "text-accent-bright",
                  )}
                >
                  {b.kind} · {b.created_at ? new Date(b.created_at).toLocaleDateString() : ""}
                </p>
              </Link>
            ))
          )}
        </div>
      </section>

      <Link
        href="/research"
        className="flex items-center gap-2 rounded-xl border border-accent/30 bg-accent-dim px-3.5 py-2.5 text-sm text-muted transition hover:border-accent"
      >
        <span className="text-accent-bright">✦</span>
        <span className="flex-1 truncate">Ask the analyst anything…</span>
        <span className="rounded bg-accent-bright px-2 py-0.5 text-[10px] font-bold text-bg">
          GO
        </span>
      </Link>
    </aside>
  );
}
