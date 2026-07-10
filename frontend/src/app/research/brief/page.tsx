"use client";

// Brief detail — real analyst output: body, citations, and the graded claim.
// Query-param route (/research/brief?id=...) because brief ids are dynamic
// UUIDs and the app builds with output:"export" (no server-side params).
import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { API_BASE } from "@/lib/alphaedge-api";
import { fetchBrief, type AnalystBrief } from "@/lib/polyscout-api";
import { QuestWhyBrief } from "@/components/quest/QuestWhyBrief";
import { QuestBriefReport } from "@/components/quest/QuestBriefReport";
import { BriefEvidencePanel } from "@/components/BriefEvidencePanel";
import BriefBySlugClient from "./[slug]/brief-client";
import { ClaimBadge } from "@/components/ClaimBadge";

type PredictionContext = {
  model_prob?: number | null;
  market_implied?: number | null;
  edge?: number | null;
  ensemble?: AnalystBrief["ensemble"];
};

type PredictionResponse = {
  predicted_prob?: number;
  edge?: number;
  ensemble?: AnalystBrief["ensemble"];
};

type ExplainResponse = {
  model_prob?: number;
  market_implied?: number;
  edge?: number;
};

function BriefDetailInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  const slug = searchParams.get("slug");
  const [brief, setBrief] = useState<AnalystBrief | null | undefined>(undefined);
  const [context, setContext] = useState<PredictionContext | null>(null);

  useEffect(() => {
    if (!id) {
      setBrief(null);
      setContext(null);
      return;
    }
    let dead = false;
    void fetchBrief(id).then(async (next) => {
      if (dead) return;
      setBrief(next);
      const nextContext = next ? await fetchPredictionContext(next.market_slug) : null;
      if (!dead) setContext(nextContext);
    });
    return () => {
      dead = true;
    };
  }, [id]);

  // Live-market entry point (?slug=pm-…): dynamic slugs can't be prerendered
  // under the static export, so resolve-or-run the analyst here instead.
  if (!id && slug) {
    return <BriefBySlugClient slug={slug} />;
  }

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
    <QuestBriefReport
      brief={brief}
      claimSlot={
        <>
          {brief.claim ? <ClaimBadge claim={brief.claim} /> : null}
          {brief.persona ? (
            <span
              className="rounded-pill bg-accent-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent-bright"
              title="Analyst lens used for this brief"
            >
              {brief.persona === "whale-flow"
                ? "whale flow"
                : brief.persona === "macro"
                  ? "macro desk"
                  : "news desk"}
            </span>
          ) : null}
          <span className="rounded-pill bg-surface-2 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-muted">
            {brief.generator === "llm" ? brief.model_version : "deterministic fallback"}
          </span>
        </>
      }
      evidenceSlot={
        <>
          <BriefEvidencePanel brief={brief} context={context} />
          {brief.claim ? (
            <section className="mt-8 rounded-2xl border border-accent/30 bg-accent-dim p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-accent">
                The claim
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text">
                This brief stakes a falsifiable claim —{" "}
                <ClaimBadge claim={brief.claim} showStatus={false} /> from a price of{" "}
                <span className="font-mono">
                  {brief.claim.price_at_claim != null
                    ? `${Math.round(brief.claim.price_at_claim * 100)}¢`
                    : "n/a"}
                </span>
                . Status:{" "}
                <span className="font-mono font-semibold uppercase">{brief.claim.status}</span>
                {brief.claim.resolution_price != null ? (
                  <>
                    {" "}
                    at{" "}
                    <span className="font-mono">
                      {Math.round(brief.claim.resolution_price * 100)}¢
                    </span>
                  </>
                ) : null}
                . Every claim is graded automatically — see the{" "}
                <Link href="/track-record" className="font-semibold text-accent hover:underline">
                  track record
                </Link>
                .
              </p>
            </section>
          ) : null}
        </>
      }
      whySlot={<QuestWhyBrief brief={brief} />}
    />
  );
}

async function fetchPredictionContext(slug: string): Promise<PredictionContext | null> {
  if (!API_BASE) return null;
  const encoded = encodeURIComponent(slug);
  const [prediction, explain] = await Promise.all([
    fetchOptionalJson<PredictionResponse>(`/api/v1/markets/${encoded}/prediction`),
    fetchOptionalJson<ExplainResponse>(`/api/v1/markets/${encoded}/explain`),
  ]);
  if (!prediction && !explain) return null;
  const modelProb = explain?.model_prob ?? prediction?.predicted_prob ?? null;
  const edge = explain?.edge ?? prediction?.edge ?? null;
  const marketImplied =
    explain?.market_implied ??
    (typeof modelProb === "number" && typeof edge === "number" ? modelProb - edge : null);
  return {
    model_prob: modelProb,
    market_implied: marketImplied,
    edge,
    ensemble: prediction?.ensemble ?? null,
  };
}

async function fetchOptionalJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
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
