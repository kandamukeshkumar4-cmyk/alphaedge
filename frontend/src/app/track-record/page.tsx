"use client";

// Public track record — the AI's scoreboard from GET /api/v1/analyst/track-record.
// Misses render as prominently as wins: transparency IS the product.
import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchGradedClaims,
  fetchTrackRecord,
  type BriefClaim,
  type TrackRecordRow,
} from "@/lib/polyscout-api";
import { ClaimBadge } from "@/components/ClaimBadge";
import { TrackRecordReliability } from "@/components/TrackRecordReliability";
import { cn } from "@/lib/cn";

const WINDOW_LABEL: Record<number, string> = { 7: "7 days", 30: "30 days", 0: "All time" };

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function ScoreCard({ row }: { row: TrackRecordRow }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-2">
        {WINDOW_LABEL[row.window_days] ?? `${row.window_days} days`}
      </p>
      <p className="mt-2 font-mono text-3xl font-semibold text-text">{pct(row.accuracy)}</p>
      <div className="mt-1.5 flex items-center gap-2 text-xs text-muted">
        <span className="font-mono">Brier {Number(row.brier).toFixed(3)}</span>
        <span className="font-mono">n={row.n}</span>
        {row.provisional && (
          <span
            className="rounded-pill bg-secondary-dim px-2 py-0.5 font-mono text-[10px] font-semibold text-gold"
            title="Fewer than 30 graded claims — treat with caution"
          >
            PROVISIONAL
          </span>
        )}
      </div>
    </div>
  );
}

export default function TrackRecordPage() {
  const [rows, setRows] = useState<TrackRecordRow[] | null>(null);
  const [claims, setClaims] = useState<BriefClaim[] | null>(null);

  useEffect(() => {
    void fetchTrackRecord().then(setRows);
    void fetchGradedClaims({ limit: 50 }).then(setClaims);
  }, []);

  const overall = (rows ?? []).filter((r) => r.dimension === "overall");
  const byDimension = (dim: string) =>
    (rows ?? []).filter((r) => r.dimension === dim && r.window_days === 0);

  const breakdowns: Array<{ title: string; rows: TrackRecordRow[] }> = [
    { title: "By category", rows: byDimension("category") },
    { title: "By claim type", rows: byDimension("claim_type") },
    { title: "By model version", rows: byDimension("model_version") },
    { title: "By prompt version", rows: byDimension("prompt_version") },
  ].filter((b) => b.rows.length > 0);

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-6">
      <div className="mb-1 flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Track record</h1>
        <span className="rounded-pill bg-accent-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent">
          GRADED BY REALITY
        </span>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-muted">
        Every claim the analyst stakes is graded against actual market prices with strict
        no-lookahead rules — the horizon price can only come from data inside the claim
        window. Wins and misses both count. Nothing is curated.
      </p>

      {rows === null ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-surface" />
          ))}
        </div>
      ) : overall.length === 0 ? (
        <div className="rounded-2xl border border-border bg-surface p-10 text-center">
          <p className="text-base font-semibold text-text">No graded claims yet</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
            Claims grade automatically once their horizon passes. Check the{" "}
            <Link href="/research" className="font-semibold text-accent hover:underline">
              research feed
            </Link>{" "}
            for pending claims.
          </p>
        </div>
      ) : null}

      <section className="mt-8">
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Forecast reliability
          </h2>
          <span className="rounded-pill bg-secondary-dim px-2 py-0.5 font-mono text-[10px] font-semibold text-accent">
            REAL RESOLUTIONS ONLY
          </span>
          <Link
            href="/resolved"
            className="ml-auto text-xs font-semibold text-accent hover:underline"
          >
            Browse resolved markets →
          </Link>
          <Link
            href="/backtest"
            className="text-xs font-semibold text-accent hover:underline"
          >
            See backtest methodology →
          </Link>
        </div>
        <TrackRecordReliability />
      </section>

      {rows === null ? null : overall.length === 0 ? null : (
        <div className="grid gap-3 sm:grid-cols-3">
          {[7, 30, 0].map((w) => {
            const row = overall.find((r) => r.window_days === w);
            return row ? <ScoreCard key={w} row={row} /> : null;
          })}
        </div>
      )}

      {breakdowns.map((b) => (
        <section key={b.title} className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            {b.title}
          </h2>
          <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-2">
                  <th className="px-4 py-2.5 font-semibold">Segment</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Accuracy</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Brier</th>
                  <th className="px-4 py-2.5 text-right font-semibold">n</th>
                </tr>
              </thead>
              <tbody>
                {b.rows.map((r) => (
                  <tr key={r.dim_key} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2.5 font-medium text-text">
                      {r.dim_key}
                      {r.provisional && (
                        <span className="ml-2 rounded-pill bg-secondary-dim px-1.5 py-0.5 font-mono text-[9px] font-semibold text-gold">
                          PROV
                        </span>
                      )}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-2.5 text-right font-mono",
                        r.accuracy >= 0.5 ? "text-up" : "text-down",
                      )}
                    >
                      {pct(r.accuracy)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-muted">
                      {Number(r.brier).toFixed(3)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-muted-2">{r.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
          Recent graded claims — wins and misses
        </h2>
        {claims === null ? (
          <div className="h-40 animate-pulse rounded-2xl border border-border bg-surface" />
        ) : claims.length === 0 ? (
          <p className="rounded-2xl border border-border bg-surface p-6 text-center text-sm text-muted">
            No claims graded yet.
          </p>
        ) : (
          <div className="space-y-2">
            {claims.map((c) => (
              <Link
                key={c.id}
                href={marketHref(c.market_slug)}
                className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 transition hover:border-accent/50"
              >
                <ClaimBadge claim={c} />
                <span className="font-mono text-xs text-muted">{c.market_slug}</span>
                <span className="ml-auto text-xs text-muted-2">
                  {c.resolved_at
                    ? new Date(c.resolved_at).toLocaleDateString()
                    : new Date(c.created_at).toLocaleDateString()}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
