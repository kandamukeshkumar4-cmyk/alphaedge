"use client";

// Research feed — every card is a real AI-analyst brief from GET /api/v1/briefs.
// No mock data: with the backend down this renders an honest empty state.
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { fetchBriefs, type AnalystBrief } from "@/lib/polyscout-api";
import { ClaimBadge } from "@/components/ClaimBadge";
import { cn } from "@/lib/cn";

const KINDS = [
  { id: "", label: "All" },
  { id: "brief", label: "Briefs" },
  { id: "digest", label: "Daily digests" },
] as const;

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function BriefCard({ brief }: { brief: AnalystBrief }) {
  return (
    <Link
      href={`/research/brief?id=${brief.id}`}
      className="group block rounded-2xl border border-border bg-surface p-5 transition hover:border-accent/50 hover:shadow-card"
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-pill bg-surface-2 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-muted">
          {brief.market_slug}
        </span>
        {brief.kind === "digest" && (
          <span className="rounded-pill bg-secondary-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-gold">
            DAILY DIGEST
          </span>
        )}
        {brief.claim && <ClaimBadge claim={brief.claim} />}
        <span className="ml-auto text-xs text-muted-2">{timeAgo(brief.created_at)}</span>
      </div>
      <h3 className="text-base font-semibold leading-snug text-text group-hover:text-white">
        {brief.headline}
      </h3>
      <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">
        {brief.body_markdown.replace(/[#*_>`]/g, "").slice(0, 220)}
      </p>
      <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-2">
        <span className="font-mono">{brief.citations.length} citation{brief.citations.length === 1 ? "" : "s"}</span>
        <span className="font-mono">{brief.generator === "llm" ? brief.model_version : "deterministic"}</span>
        <span className="ml-auto font-semibold text-accent opacity-0 transition group-hover:opacity-100">
          Read brief →
        </span>
      </div>
    </Link>
  );
}

export default function ResearchPage() {
  const [briefs, setBriefs] = useState<AnalystBrief[] | null>(null);
  const [kind, setKind] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const LIMIT = 20;

  const load = useCallback(async (k: string, o: number) => {
    const page = await fetchBriefs({ kind: k || undefined, limit: LIMIT, offset: o });
    setBriefs((prev) => (o === 0 ? page.items : [...(prev ?? []), ...page.items]));
    setTotal(page.total);
  }, []);

  useEffect(() => {
    setBriefs(null);
    setOffset(0);
    void load(kind, 0);
  }, [kind, load]);

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-6">
      <div className="mb-1 flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Research</h1>
        <span className="rounded-pill bg-accent-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent">
          AI ANALYST
        </span>
      </div>
      <p className="mb-6 max-w-2xl text-sm text-muted">
        Briefs are generated when independent signals align — price moves, smart-money
        wallets, unpriced news. Every brief cites its evidence and stakes a claim that
        gets graded on the{" "}
        <Link href="/track-record" className="font-semibold text-accent hover:underline">
          public track record
        </Link>
        .
      </p>

      <div className="mb-5 flex gap-1.5">
        {KINDS.map((k) => (
          <button
            key={k.id}
            type="button"
            onClick={() => setKind(k.id)}
            className={cn(
              "rounded-pill px-4 py-1.5 text-sm font-semibold transition",
              kind === k.id
                ? "bg-text text-bg"
                : "text-muted hover:bg-surface hover:text-text",
            )}
          >
            {k.label}
          </button>
        ))}
      </div>

      {briefs === null ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-2xl border border-border bg-surface" />
          ))}
        </div>
      ) : briefs.length === 0 ? (
        <div className="rounded-2xl border border-border bg-surface p-10 text-center">
          <p className="text-base font-semibold text-text">No briefs yet</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
            The analyst writes a brief when at least three signal layers align on one
            market. Watch the{" "}
            <Link href="/signals" className="font-semibold text-accent hover:underline">
              signal feed
            </Link>{" "}
            to see the layers forming.
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {briefs.map((b) => (
              <BriefCard key={b.id} brief={b} />
            ))}
          </div>
          {briefs.length < total && (
            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => {
                  const next = offset + LIMIT;
                  setOffset(next);
                  void load(kind, next);
                }}
                className="rounded-pill border border-border px-6 py-2.5 text-sm font-semibold text-muted transition hover:border-accent hover:text-text"
              >
                Load more
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
