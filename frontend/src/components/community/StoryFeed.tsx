"use client";

import { useEffect, useState } from "react";

import { StoryCard } from "@/components/community/StoryCard";
import { listStories, type Story } from "@/lib/social-api";
import { useAuth } from "@/hooks/useAuth";

const PAGE_SIZE = 20;

function StorySkeleton() {
  return (
    <article
      aria-hidden="true"
      className="min-h-[150px] rounded-2xl border border-border bg-surface p-4"
    >
      <header className="flex items-center gap-3">
        <span className="h-9 w-9 shrink-0 animate-pulse rounded-full bg-surface-3" />
        <span className="flex-1">
          <span className="block h-3 w-32 animate-pulse rounded bg-surface-3" />
          <span className="mt-2 block h-2.5 w-20 animate-pulse rounded bg-surface-3" />
        </span>
      </header>
      <span className="mt-5 block h-4 w-4/5 animate-pulse rounded bg-surface-3" />
      <span className="mt-3 block h-3 w-2/5 animate-pulse rounded bg-surface-3" />
    </article>
  );
}

export function StoryFeed() {
  const { token, isReady } = useAuth();
  const [stories, setStories] = useState<Story[] | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady) return;
    let cancelled = false;
    setStories(null);
    setNextCursor(null);
    setError(null);

    void listStories(PAGE_SIZE, null, token).then(
      ({ data }) => {
        if (cancelled) return;
        setStories(data.items);
        setNextCursor(data.next_cursor);
      },
      () => {
        if (!cancelled) {
          setStories([]);
          setError("The community feed is unavailable right now.");
        }
      },
    );

    return () => {
      cancelled = true;
    };
  }, [isReady, token]);

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    const cursor = nextCursor;
    setLoadingMore(true);
    setError(null);
    try {
      const { data } = await listStories(PAGE_SIZE, cursor, token);
      setStories((current) => [...(current ?? []), ...data.items]);
      setNextCursor(data.next_cursor);
    } catch {
      setError("More stories could not be loaded. Try again.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <main id="community-feed" className="min-h-screen bg-bg">
      <section className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
        <header className="mb-6">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
            Community desk
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-text">Stories from the desk</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
            Paper-market notes, forecasts, and shared context from the AlphaEdge community.
          </p>
        </header>

        {error ? (
          <p
            role="alert"
            className="mb-4 rounded-xl border border-danger/30 bg-danger-dim px-4 py-3 text-sm text-danger"
          >
            {error}
          </p>
        ) : null}

        {stories === null ? (
          <section aria-label="Loading community stories" className="space-y-3">
            {Array.from({ length: 4 }, (_, index) => (
              <StorySkeleton key={index} />
            ))}
          </section>
        ) : stories.length === 0 ? (
          <section
            data-testid="community-empty-state"
            className="rounded-2xl border border-border bg-surface px-6 py-12 text-center"
          >
            <p className="text-base font-black text-text">No stories yet</p>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted">
              Community notes will appear here as paper-market research is shared.
            </p>
          </section>
        ) : (
          <section aria-label="Community stories" className="space-y-3">
            {stories.map((story) => (
              <StoryCard key={story.id} story={story} />
            ))}
            {nextCursor ? (
              <button
                type="button"
                onClick={() => void loadMore()}
                disabled={loadingMore}
                className="mt-2 inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-border bg-surface px-4 py-2 text-sm font-bold text-muted transition hover:border-primary/50 hover:text-text disabled:cursor-wait disabled:opacity-60"
              >
                {loadingMore ? "Loading more stories…" : "Load more"}
              </button>
            ) : null}
          </section>
        )}
      </section>
    </main>
  );
}
