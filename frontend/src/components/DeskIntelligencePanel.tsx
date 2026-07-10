"use client";

// D01: single-call Intelligence panel for the market detail page.
// ONE GET /api/v1/desk?slug= renders: model-vs-market edge chip, smart-money
// mini-summary (concentration + last large flow), arb-match chip, and the
// latest signals with the shared F04 evidence renderer. Honest per-section
// empties; analysis only — no order controls (the trading panel is separate).
import Link from "next/link";
import { useEffect, useState } from "react";
import { buildDeskView, fetchDesk, type DeskView } from "@/lib/desk-api";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { cn } from "@/lib/cn";

function timeLabel(iso: string): string {
  const ts = Date.parse(iso);
  if (!ts) return "";
  const mins = Math.max(0, Math.round((Date.now() - ts) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

const EDGE_TONE: Record<"up" | "down" | "neutral", string> = {
  up: "text-up",
  down: "text-danger",
  neutral: "text-muted",
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">
      {children}
    </p>
  );
}

export function DeskIntelligencePanel({ slug }: { slug: string }) {
  const [view, setView] = useState<DeskView | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Fetch-on-load only (no poll loop) — the aggregate replaces the page's
    // separate edge/signals fetches with a single request.
    const ctrl = new AbortController();
    setLoaded(false);
    void fetchDesk(slug, { signal: ctrl.signal }).then((raw) => {
      setView(buildDeskView(raw));
      setLoaded(true);
    });
    return () => ctrl.abort();
  }, [slug]);

  if (!loaded) {
    return (
      <section
        id="intelligence"
        aria-label="Market intelligence"
        className="scroll-mt-28 rounded-2xl border border-border bg-surface p-4"
      >
        <div className="skeleton h-40 w-full rounded-xl" aria-hidden />
      </section>
    );
  }

  if (!view || !view.found) {
    return (
      <section
        id="intelligence"
        aria-label="Market intelligence"
        className="scroll-mt-28 rounded-2xl border border-border bg-surface p-4"
      >
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Intelligence</h2>
        <p className="mt-2 text-xs leading-relaxed text-muted">
          {view === null || view.slug === ""
            ? "Desk aggregate unreachable — live intelligence needs the backend API."
            : "No desk intelligence for this market yet — the aggregate covers locally mirrored markets only."}
        </p>
      </section>
    );
  }

  const sm = view.smartMoney;

  return (
    <section
      id="intelligence"
      aria-label="Market intelligence"
      className="scroll-mt-28 rounded-2xl border border-border bg-surface p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Intelligence</h2>
        <div className="flex items-center gap-2">
          {/* Z03: share affordance → read-only /s/[slug] snapshot page. */}
          <Link
            href={`/s/${encodeURIComponent(view.slug)}`}
            aria-label="Open shareable snapshot for this market"
            className="rounded-lg border border-border px-2 py-0.5 text-[11px] font-semibold text-accent transition hover:border-border-light hover:underline"
          >
            Share ↗
          </Link>
          <span className="rounded-pill border border-border px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-muted-2">
            Signal only
          </span>
        </div>
      </div>

      {/* Model-vs-market edge chip */}
      <div className="mt-3">
        <SectionTitle>Model vs market</SectionTitle>
        {view.edge ? (
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-sm font-black text-text">
              model {view.edge.modelLabel}
            </span>
            {view.edge.edgeLabel ? (
              <span
                className={cn(
                  "rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-sm font-black",
                  EDGE_TONE[view.edge.edgeTone],
                )}
              >
                {view.edge.edgeLabel} vs book
              </span>
            ) : (
              <span className="text-[11px] text-muted-2">no book reference price</span>
            )}
            {view.edge.confidenceLabel ? (
              <span className="font-mono text-[11px] text-muted-2">
                {view.edge.confidenceLabel}
              </span>
            ) : null}
          </div>
        ) : (
          <p className="mt-1.5 text-xs text-muted">No model prediction logged for this market yet.</p>
        )}
      </div>

      {/* Smart-money mini-summary */}
      <div className="mt-4">
        <div className="flex items-center justify-between gap-2">
          <SectionTitle>Smart money</SectionTitle>
          <Link
            href={`/smart-money?slug=${encodeURIComponent(view.slug)}`}
            className="text-[11px] font-semibold text-accent hover:underline"
          >
            Full view →
          </Link>
        </div>
        {sm.found ? (
          <div className="mt-1.5 space-y-1.5">
            <p className="text-xs text-muted">
              Concentration{" "}
              <span className="font-mono font-bold text-text">{sm.concentrationLabel}</span>
              <span className="text-muted-2"> · {sm.walletCountLabel} wallets</span>
            </p>
            {sm.lastFlow ? (
              <p className="text-xs text-muted">
                Last large flow:{" "}
                <span className="font-mono text-text">{sm.lastFlow.wallet}</span>{" "}
                <span
                  className={cn(
                    "font-mono font-bold",
                    sm.lastFlow.isBuy ? "text-up" : "text-danger",
                  )}
                >
                  {sm.lastFlow.direction} {sm.lastFlow.outcome}
                </span>{" "}
                <span className="font-mono text-muted-2">{sm.lastFlow.sizeLabel}</span>
              </p>
            ) : (
              <p className="text-xs text-muted-2">No large flows in the window.</p>
            )}
            {sm.errors.map((e) => (
              <p key={e} className="text-[11px] text-gold">
                Partial data: {e}
              </p>
            ))}
          </div>
        ) : (
          <p className="mt-1.5 text-xs text-muted-2">No smart-money observations yet.</p>
        )}
      </div>

      {/* Arb-match chip (only when a venue match exists) */}
      {view.arb ? (
        <div className="mt-4">
          <div className="flex items-center justify-between gap-2">
            <SectionTitle>Cross-venue match</SectionTitle>
            <Link href="/arb" className="text-[11px] font-semibold text-accent hover:underline">
              Arb desk →
            </Link>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="max-w-full truncate rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-[11px] text-text">
              {view.arb.counterpartTitle}
            </span>
            <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-[11px] font-bold text-accent">
              {view.arb.confidenceLabel} match
            </span>
            {view.arb.spreadNote ? (
              <span className="font-mono text-[11px] text-muted-2">{view.arb.spreadNote}</span>
            ) : null}
            {view.arb.stale ? (
              <span className="rounded-pill bg-surface-3 px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-muted">
                stale
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Latest signals with F04 evidence */}
      <div className="mt-4">
        <SectionTitle>Latest signals</SectionTitle>
        {view.hasSignals ? (
          <ul className="mt-1.5 space-y-2">
            {view.signals.map((s) => (
              <li key={s.id} className="rounded-lg border border-border/60 px-2.5 py-2">
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-[11px] font-bold uppercase tracking-wide text-text">
                    {s.typeLabel}
                  </span>
                  <span className="shrink-0 text-[10px] text-muted-2">
                    {timeLabel(s.createdAt)}
                  </span>
                </div>
                {s.evidence ? <SignalEvidenceBlock evidence={s.evidence} /> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1.5 text-xs text-muted-2">
            No signals for this market yet — scans publish only when a real trigger fires.
          </p>
        )}
      </div>

      {/* D03: cross-links to the sibling intelligence surfaces */}
      <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 border-t border-border pt-3">
        <Link
          href={`/smart-money?slug=${encodeURIComponent(view.slug)}`}
          className="text-[11px] font-semibold text-accent hover:underline"
        >
          Smart money →
        </Link>
        <Link href="/arb" className="text-[11px] font-semibold text-accent hover:underline">
          Arb desk →
        </Link>
        <Link href="/track-record" className="text-[11px] font-semibold text-accent hover:underline">
          Track record →
        </Link>
      </div>

      <p className="mt-3 text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
    </section>
  );
}
