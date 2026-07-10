"use client";

// Z02 — Shareable snapshot card (backend M02). Read-only intelligence for one
// market: title, YES price, model-vs-market edge one-liner, top signal (H03
// evidence), cross-venue arb flag, and a smart-money one-liner, with a
// "View full market →" link and a "Copy link" button (copies the /s/[slug] URL).
// Honest unreachable / not-found / thin states. Research only, paper trading
// only — a shareable read, never a trade. Fetch-on-load only (no poll loop).
import Link from "next/link";
import { useEffect, useState } from "react";

import { AnimatedNumber } from "@/components/AnimatedNumber";
import { MotionReveal } from "@/components/MotionReveal";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { PageShell } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";
import {
  buildShareSnapshotView,
  fetchShareSnapshot,
  type ShareSnapshotView,
} from "@/lib/share-snapshot-api";

const EDGE_TONE: Record<"up" | "down" | "neutral", string> = {
  up: "text-up",
  down: "text-danger",
  neutral: "text-muted",
};

function CopyLinkButton({ slug }: { slug: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    const url =
      typeof window !== "undefined"
        ? `${window.location.origin}/s/${encodeURIComponent(slug)}`
        : `/s/${encodeURIComponent(slug)}`;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(url);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label="Copy share link"
      className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-bold text-text transition hover:border-border-light"
    >
      {copied ? "Copied ✓" : "Copy link"}
    </button>
  );
}

function Loading() {
  return (
    <div aria-hidden className="rounded-2xl border border-border bg-surface p-6">
      <div className="skeleton h-5 w-2/3 rounded" />
      <div className="skeleton mt-4 h-10 w-32 rounded" />
      <div className="skeleton mt-4 h-16 w-full rounded-lg" />
      <div className="skeleton mt-3 h-12 w-full rounded-lg" />
    </div>
  );
}

function SnapshotCard({ view }: { view: ShareSnapshotView }) {
  return (
    <MotionReveal className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-primary">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.8)]" />
            Shareable snapshot
          </p>
          <h1 className="mt-2 text-xl font-black tracking-tight text-text sm:text-2xl">{view.title}</h1>
          <p className="mt-1 font-mono text-[11px] text-muted-2">{view.slug}</p>
        </div>
        <span className="shrink-0 rounded-pill border border-border px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-muted-2">
          Signal only
        </span>
      </div>

      {/* YES price + edge one-liner */}
      <div className="mt-5 flex flex-wrap items-end gap-x-6 gap-y-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">YES price</p>
          {view.yesLabel ? (
            <p className="mt-1 font-mono text-3xl font-black tabular-nums text-text">{view.yesLabel}</p>
          ) : (
            <p className="mt-1 text-sm text-muted-2">No odds snapshot yet</p>
          )}
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Model vs market</p>
          {view.edgeLabel || view.modelLabel ? (
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-sm font-bold">
              {view.modelLabel ? <span className="text-text">model {view.modelLabel}</span> : null}
              {view.marketLabel ? <span className="text-muted">market {view.marketLabel}</span> : null}
              {view.edgeLabel ? (
                <span className={cn("font-black", EDGE_TONE[view.edgeTone])}>edge {view.edgeLabel}</span>
              ) : null}
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted-2">No model prediction logged yet</p>
          )}
        </div>
      </div>

      {/* Cross-venue arb flag */}
      {view.arbMatched ? (
        <div className="mt-4">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent/12 px-2.5 py-1 font-mono text-[11px] font-black text-accent">
            Cross-venue arb match
          </span>
        </div>
      ) : null}

      {/* Smart-money one-liner */}
      <div className="mt-5">
        <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Smart money</p>
        {view.smartMoneyNote ? (
          <p className="mt-1 text-sm leading-relaxed text-muted">{view.smartMoneyNote}</p>
        ) : (
          <p className="mt-1 text-sm text-muted-2">No smart-money activity to report.</p>
        )}
      </div>

      {/* Top signal with H03 evidence */}
      <div className="mt-5">
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Top signal</p>
          {view.topSignal ? (
            <>
              <span className="rounded bg-accent-dim px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-accent-bright">
                {view.topSignal.familyLabel}
              </span>
              {view.topSignal.timeLabel ? (
                <span className="ml-auto text-[10px] text-muted-2">{view.topSignal.timeLabel}</span>
              ) : null}
            </>
          ) : null}
        </div>
        {view.topSignal ? (
          <>
            <p className="mt-1.5 text-[11px] font-bold uppercase tracking-wide text-text">
              {view.topSignal.typeLabel}
            </p>
            {view.topSignal.evidence ? (
              <SignalEvidenceBlock evidence={view.topSignal.evidence} />
            ) : null}
          </>
        ) : (
          <p className="mt-1.5 text-sm text-muted-2">
            No signals for this market yet — scans publish only when a real trigger fires.
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-4">
        <Link
          href={marketHref(view.slug)}
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
        >
          View full market →
        </Link>
        <CopyLinkButton slug={view.slug} />
      </div>

      <p className="mt-5 text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
    </MotionReveal>
  );
}

function NotFoundCard({ view }: { view: ShareSnapshotView }) {
  const unreachable = !view.reachable;
  return (
    <div className="rounded-2xl border border-border bg-surface p-8 text-center">
      <p className="text-sm font-semibold text-text">
        {unreachable ? "Snapshot unreachable" : "No snapshot for this market"}
      </p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">
        {unreachable
          ? "The snapshot API did not answer — start the backend or set NEXT_PUBLIC_API_URL to see this share card."
          : "This market is not in the desk catalog, so there is no intelligence to share. Nothing is fabricated."}
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/markets"
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
        >
          Browse markets
        </Link>
        <Link href="/home" className="text-xs font-semibold text-accent hover:underline">
          Go to Home
        </Link>
      </div>
    </div>
  );
}

export default function ShareSnapshotClient({ slug }: { slug: string }) {
  const [view, setView] = useState<ShareSnapshotView | null>(null);

  useEffect(() => {
    let dead = false;
    const ctrl = new AbortController();
    setView(null);
    void fetchShareSnapshot(slug, { signal: ctrl.signal }).then((raw) => {
      if (dead || ctrl.signal.aborted) return;
      setView(buildShareSnapshotView(raw));
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [slug]);

  return (
    <PageShell width="narrow">
      <section aria-label="Shareable market snapshot" className="mx-auto max-w-2xl">
        {view === null ? (
          <Loading />
        ) : view.reachable && view.found ? (
          <SnapshotCard view={view} />
        ) : (
          <NotFoundCard view={view} />
        )}
      </section>
    </PageShell>
  );
}
