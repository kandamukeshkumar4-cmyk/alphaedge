"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { FeedFilterBar } from "@/components/FeedFilterBar";
import { UnifiedFeed } from "@/components/UnifiedFeed";

function FeedPageInner() {
  const params = useSearchParams();
  const activeType = params.get("type") ?? "";
  const activePlatform = params.get("platform") ?? "";

  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text">Activity Feed</h1>
          <p className="mt-1 text-sm text-muted">
            Cross-market stream: alignment triggers, whale moves, news signals, analyst briefs and graded claims.
          </p>
        </div>

        {/* Filters — persisted in URL params */}
        <FeedFilterBar activeType={activeType} activePlatform={activePlatform} />

        {/* Feed */}
        <UnifiedFeed activeType={activeType} activePlatform={activePlatform} />
      </div>
    </main>
  );
}

export default function FeedPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-bg">
          <div className="mx-auto max-w-3xl px-4 py-8">
            <div className="h-8 w-48 animate-pulse rounded bg-surface" />
            <div className="mt-2 h-4 w-80 animate-pulse rounded bg-surface" />
            <div className="mt-6 h-9 animate-pulse rounded-lg bg-surface" />
            <div className="mt-4 space-y-3">
              {Array.from({ length: 5 }, (_, i) => (
                <div key={i} className="h-24 animate-pulse rounded-xl border border-border bg-surface" />
              ))}
            </div>
          </div>
        </main>
      }
    >
      <FeedPageInner />
    </Suspense>
  );
}
