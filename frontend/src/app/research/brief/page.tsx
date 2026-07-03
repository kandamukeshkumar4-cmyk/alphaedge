"use client";

// Brief detail — real analyst output: body, citations, and the graded claim.
// Query-param route (/research/brief?id=...) because brief ids are dynamic
// UUIDs and the app builds with output:"export" (no server-side params).
import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchBrief, type AnalystBrief } from "@/lib/polyscout-api";
import { QuestWhyBrief } from "@/components/quest/QuestWhyBrief";
import { ClaimBadge } from "@/components/ClaimBadge";

function renderMarkdownish(md: string): React.ReactNode[] {
  // Minimal renderer: headings, bold, paragraphs, list items. No HTML injection.
  return md.split(/\n{1,}/).map((block, i) => {
    const t = block.trim();
    if (!t) return null;
    if (t.startsWith("### ")) {
      return (
        <h3 key={i} className="mt-5 text-base font-semibold text-text">
          {t.slice(4)}
        </h3>
      );
    }
    if (t.startsWith("## ")) {
      return (
        <h2 key={i} className="mt-6 text-lg font-semibold text-text">
          {t.slice(3)}
        </h2>
      );
    }
    if (t.startsWith("- ")) {
      return (
        <li key={i} className="ml-5 list-disc text-sm leading-relaxed text-muted">
          {t.slice(2)}
        </li>
      );
    }
    return (
      <p key={i} className="mt-3 text-sm leading-relaxed text-muted">
        {t}
      </p>
    );
  });
}

function BriefDetailInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  const [brief, setBrief] = useState<AnalystBrief | null | undefined>(undefined);

  useEffect(() => {
    if (!id) {
      setBrief(null);
      return;
    }
    void fetchBrief(id).then(setBrief);
  }, [id]);

  if (brief === undefined) {
    return (
      <main className="mx-auto max-w-[800px] px-4 py-8 sm:px-6">
        <div className="h-64 animate-pulse rounded-2xl border border-border bg-surface" />
      </main>
    );
  }

  if (brief === null) {
    return (
      <main className="mx-auto max-w-[800px] px-4 py-16 text-center sm:px-6">
        <p className="text-lg font-semibold text-text">Brief not found</p>
        <p className="mt-2 text-sm text-muted">
          It may not exist, or the backend is unreachable.
        </p>
        <Link
          href="/research"
          className="mt-5 inline-block rounded-pill bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-active"
        >
          Back to research
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[800px] px-4 py-8 sm:px-6">
      <nav className="mb-4 text-xs text-muted-2" aria-label="Breadcrumb">
        <Link href="/research" className="hover:text-text">
          Research
        </Link>
        <span className="mx-1.5">/</span>
        <Link
          href={marketHref(brief.market_slug)}
          className="font-mono hover:text-text"
        >
          {brief.market_slug}
        </Link>
      </nav>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        {brief.claim && <ClaimBadge claim={brief.claim} />}
        <span className="rounded-pill bg-surface-2 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-muted">
          {brief.generator === "llm" ? brief.model_version : "deterministic fallback"}
        </span>
        <span className="rounded-pill bg-surface-2 px-2.5 py-0.5 font-mono text-[11px] text-muted-2">
          prompt {brief.prompt_version}
        </span>
      </div>

      <h1 className="text-2xl font-semibold leading-tight tracking-tight text-text">
        {brief.headline}
      </h1>
      <p className="mt-1 text-xs text-muted-2">
        {new Date(brief.created_at).toLocaleString()}
      </p>

      <article className="mt-4">{renderMarkdownish(brief.body_markdown)}</article>

      {brief.claim && (
        <section className="mt-8 rounded-2xl border border-accent/30 bg-accent-dim p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-accent">
            The claim
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-text">
            This brief stakes a falsifiable claim — <ClaimBadge claim={brief.claim} showStatus={false} /> from a
            price of{" "}
            <span className="font-mono">
              {brief.claim.price_at_claim != null
                ? `${Math.round(brief.claim.price_at_claim * 100)}¢`
                : "n/a"}
            </span>
            . Status:{" "}
            <span className="font-mono font-semibold uppercase">{brief.claim.status}</span>
            {brief.claim.resolution_price != null && (
              <>
                {" "}at{" "}
                <span className="font-mono">
                  {Math.round(brief.claim.resolution_price * 100)}¢
                </span>
              </>
            )}
            . Every claim is graded automatically against market data with no lookahead —
            see the{" "}
            <Link href="/track-record" className="font-semibold text-accent hover:underline">
              track record
            </Link>
            .
          </p>
        </section>
      )}

      <QuestWhyBrief brief={brief} />

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Citations ({brief.citations.length})
        </h2>
        <ul className="mt-3 space-y-2">
          {brief.citations.map((c, i) => (
            <li
              key={i}
              className="rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-muted"
            >
              <span className="mr-2 font-mono text-[11px] font-semibold text-accent">
                [{i + 1}]
              </span>
              {String(c.label ?? c.ref ?? c.kind ?? JSON.stringify(c))}
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-8">
        <Link
          href={marketHref(brief.market_slug)}
          className="rounded-pill bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-active"
        >
          View this market →
        </Link>
      </div>
    </main>
  );
}

export default function BriefDetailPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-[800px] px-4 py-8 sm:px-6">
          <div className="h-64 animate-pulse rounded-2xl border border-border bg-surface" />
        </main>
      }
    >
      <BriefDetailInner />
    </Suspense>
  );
}
