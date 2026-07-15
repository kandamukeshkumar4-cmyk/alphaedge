"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FeedFilterBar } from "@/components/FeedFilterBar";
import { FollowedTraderFeed } from "@/components/FollowedTraderFeed";
import { UnifiedFeed } from "@/components/UnifiedFeed";

function FeedPageInner() {
  const params = useSearchParams();
  const activeType = params.get("type") ?? "";
  const activePlatform = params.get("platform") ?? "";
  const following = params.get("view") === "following";

  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text">Activity Feed</h1>
          <p className="mt-1 text-sm text-muted">
            {following
              ? "Recent paper trades from the traders you follow."
              : "Cross-market stream: alignment triggers, whale moves, news signals, analyst briefs and graded claims."}
          </p>
        </div>

        <nav className="mb-4 flex items-center gap-1 rounded-xl border border-border bg-surface p-1" aria-label="Feed views">
          <Link
            href="/feed"
            aria-current={!following ? "page" : undefined}
            className={`rounded-lg px-3 py-2 text-xs font-bold transition ${
              !following ? "bg-primary text-bg" : "text-muted hover:bg-surface-2 hover:text-text"
            }`}
          >
            All activity
          </Link>
          <Link
            href="/feed?view=following"
            aria-current={following ? "page" : undefined}
            className={`rounded-lg px-3 py-2 text-xs font-bold transition ${
              following ? "bg-primary text-bg" : "text-muted hover:bg-surface-2 hover:text-text"
            }`}
          >
            Following
          </Link>
        </nav>

        {following ? (
          <FollowedTraderFeed />
        ) : (
          <>
            <FeedFilterBar activeType={activeType} activePlatform={activePlatform} />
            <UnifiedFeed activeType={activeType} activePlatform={activePlatform} />
          </>
        )}
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
