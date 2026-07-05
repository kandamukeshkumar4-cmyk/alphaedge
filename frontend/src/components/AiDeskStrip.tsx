"use client";

// Data-first desk header. Numbers over prose: live counts from the API, the
// newest analyst briefs, and the grading scoreboard. No marketing copy.
import Link from "next/link";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";
import {
  fetchBriefs,
  fetchGradedClaims,
  fetchTrackRecord,
  type AnalystBrief,
  type TrackRecordRow,
} from "@/lib/polyscout-api";
import { ClaimBadge } from "@/components/ClaimBadge";

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

type Stats = {
  liveMarkets: number | null;
  briefs: number | null;
  pending: number | null;
  accuracy: TrackRecordRow | null;
};

function Stat({
  value,
  label,
  href,
  accent = false,
}: {
  value: string;
  label: string;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link
      href={href}
      className="group flex min-w-0 flex-col rounded-2xl border border-border bg-surface px-4 py-3 transition hover:border-accent/50"
    >
      <span
        className={`truncate font-mono text-2xl font-semibold ${accent ? "text-accent" : "text-text"}`}
      >
        {value}
      </span>
      <span className="mt-0.5 truncate text-[11px] font-medium uppercase tracking-wide text-muted-2 group-hover:text-muted">
        {label}
      </span>
    </Link>
  );
}

export function AiDeskStrip() {
  const [briefs, setBriefs] = useState<AnalystBrief[] | null>(null);
  const [stats, setStats] = useState<Stats>({
    liveMarkets: null,
    briefs: null,
    pending: null,
    accuracy: null,
  });

  useEffect(() => {
    void fetchBriefs({ kind: "brief", limit: 4 }).then((page) => {
      setBriefs(page.items);
      setStats((s) => ({ ...s, briefs: page.total }));
    });
    void fetchGradedClaims({ limit: 100 }).then((claims) => {
      setStats((s) => ({
        ...s,
        pending: claims.filter((c) => c.status === "pending").length,
      }));
    });
    void fetchTrackRecord().then((rows) => {
      setStats((s) => ({
        ...s,
        accuracy:
          rows.find((r) => r.dimension === "overall" && r.window_days === 0) ?? null,
      }));
    });
    if (API_BASE) {
      void fetch(`${API_BASE}/api/v1/markets`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : []))
        .then((d: Array<{ source?: string }>) =>
          setStats((s) => ({
            ...s,
            liveMarkets: d.filter((m) => m.source === "kalshi" || m.source === "polymarket")
              .length,
          })),
        )
        .catch(() => {});
    }
  }, []);

  return (
    <section className="border-b border-border bg-bg" data-tour="ai-desk">
      <div className="mx-auto max-w-[1280px] px-4 py-5 sm:px-6">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h1 className="flex items-center gap-2.5 text-sm font-semibold text-text">
            <span className="h-2 w-2 animate-pulse-soft rounded-full bg-up" aria-hidden />
            AI analyst desk
            <span className="hidden font-normal text-muted-2 sm:inline">
              — every call graded in public
            </span>
          </h1>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event("ae:tour"))}
            className="rounded-pill border border-border px-3.5 py-1.5 text-xs font-semibold text-muted transition hover:border-accent hover:text-text"
          >
            How it works
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
          <Stat
            value={stats.liveMarkets != null ? String(stats.liveMarkets) : "—"}
            label="Live markets"
            href="/markets"
          />
          <Stat
            value={stats.briefs != null ? String(stats.briefs) : "—"}
            label="AI briefs"
            href="/research"
            accent
          />
          <Stat
            value={stats.pending != null ? String(stats.pending) : "—"}
            label="Claims grading"
            href="/track-record"
          />
          <Stat
            value={
              stats.accuracy ? `${(stats.accuracy.accuracy * 100).toFixed(0)}%` : "—"
            }
            label={stats.accuracy ? `Accuracy · n=${stats.accuracy.n}` : "Accuracy"}
            href="/track-record"
          />

          {/* Newest briefs — compact, real */}
          <div className="col-span-2 rounded-2xl border border-border bg-surface px-4 py-3 lg:col-span-1">
            {briefs === null ? (
              <div className="h-full min-h-[52px] animate-pulse rounded-xl bg-surface-2" />
            ) : briefs.length === 0 ? (
              <Link href="/research" className="block text-sm text-muted hover:text-text">
                No briefs yet — the analyst fires when 3 signals align.
              </Link>
            ) : (
              <Link href={`/research/brief?id=${briefs[0].id}`} className="group block">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-accent">
                    Newest brief · {timeAgo(briefs[0].created_at)}
                  </span>
                  {briefs[0].claim && (
                    <ClaimBadge claim={briefs[0].claim} showStatus={false} />
                  )}
                </div>
                <p className="mt-1 line-clamp-2 text-sm font-medium leading-snug text-text group-hover:text-white">
                  {briefs[0].headline}
                </p>
              </Link>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
