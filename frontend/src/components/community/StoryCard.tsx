"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CommentThread } from "@/components/community/CommentThread";
import { useAuth } from "@/hooks/useAuth";
import { react as reactToStory, unreact, type Story, type StoryKind } from "@/lib/social-api";

const KIND_LABELS: Record<StoryKind, string> = {
  trade: "Paper trade",
  forecast: "Forecast",
  watchlist: "Watchlist",
  note: "Note",
};

const KIND_CLASSES: Record<StoryKind, string> = {
  trade: "bg-secondary-dim text-secondary",
  forecast: "bg-primary-dim text-primary",
  watchlist: "bg-accent-dim text-accent-bright",
  note: "bg-surface-3 text-muted",
};

function relativeTime(timestamp: string): string {
  const then = Date.parse(timestamp);
  if (!Number.isFinite(then)) return "Time unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(then);
}

function initials(actor: Story["actor"]): string {
  return actor.display_name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function StoryAvatar({ actor }: { actor: Story["actor"] }) {
  return actor.avatar_url ? (
    <span className="grid h-9 w-9 shrink-0 overflow-hidden rounded-full border border-border bg-surface-3">
      {/* eslint-disable-next-line @next/next/no-img-element -- avatar URLs are part of the public social contract; static export has no optimizer. */}
      <img
        src={actor.avatar_url}
        alt={`${actor.display_name} avatar`}
        width={36}
        height={36}
        loading="lazy"
        className="h-full w-full object-cover"
      />
    </span>
  ) : (
    <span
      aria-hidden="true"
      className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border bg-surface-3 font-mono text-[11px] font-bold text-muted"
    >
      {initials(actor)}
    </span>
  );
}

export function StoryCard({ story }: { story: Story }) {
  const router = useRouter();
  const { token, isReady } = useAuth();
  const [liked, setLiked] = useState(story.reacted);
  const [likeCount, setLikeCount] = useState(story.reactions.like);
  const [commentCount, setCommentCount] = useState(story.comment_count);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [likePending, setLikePending] = useState(false);
  const [likeError, setLikeError] = useState<string | null>(null);

  async function toggleLike() {
    if (!isReady) return;
    if (!token) {
      router.push(`/auth/login?next=${encodeURIComponent("/community")}`);
      return;
    }
    if (likePending) return;

    const previousLiked = liked;
    const previousCount = likeCount;
    const nextLiked = !previousLiked;
    setLikeError(null);
    setLiked(nextLiked);
    setLikeCount(Math.max(0, previousCount + (nextLiked ? 1 : -1)));
    setLikePending(true);

    try {
      const result = nextLiked
        ? await reactToStory(token, story.id)
        : await unreact(token, story.id);
      setLiked(result.data.reacted);
      setLikeCount(result.data.reactions.like);
    } catch {
      setLiked(previousLiked);
      setLikeCount(previousCount);
      setLikeError("Like could not be updated. Try again.");
    } finally {
      setLikePending(false);
    }
  }

  return (
    <article
      data-testid={`story-card-${story.id}`}
      className="rounded-2xl border border-border bg-surface p-4 transition hover:border-border-light sm:p-5"
    >
      <header className="flex items-start gap-3">
        <StoryAvatar actor={story.actor} />
        <p className="min-w-0 flex-1">
          <span className="block truncate text-sm font-bold text-text">{story.actor.display_name}</span>
          <span className="mt-0.5 block truncate text-xs text-muted-2">
            @{story.actor.handle} · <time dateTime={story.created_at}>{relativeTime(story.created_at)}</time>
          </span>
        </p>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.1em] ${KIND_CLASSES[story.kind]}`}
        >
          {KIND_LABELS[story.kind]}
        </span>
      </header>

      <p className="mt-4 text-base font-bold leading-snug text-text">{story.headline}</p>
      {story.body ? <p className="mt-2 text-sm leading-relaxed text-muted">{story.body}</p> : null}

      {story.market_slug ? (
        <Link
          href={`/markets/${encodeURIComponent(story.market_slug)}`}
          className="mt-4 inline-flex max-w-full items-center rounded-lg border border-border bg-bg/50 px-3 py-2 text-xs font-semibold text-accent-bright transition hover:border-accent/50 hover:text-text"
        >
          <span className="truncate">{story.market_title ?? story.market_slug}</span>
          <span aria-hidden="true" className="ml-2 shrink-0">→</span>
        </Link>
      ) : null}

      <footer className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/70 pt-3">
        <button
          type="button"
          onClick={() => void toggleLike()}
          disabled={likePending || !isReady}
          aria-pressed={liked}
          aria-label={liked ? "Unlike story" : "Like story"}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-xs font-bold text-muted transition hover:bg-surface-2 hover:text-text disabled:cursor-wait disabled:opacity-70"
        >
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill={liked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8">
            <path d="M20.8 8.7c0 5.2-8.8 10-8.8 10s-8.8-4.8-8.8-10A4.5 4.5 0 0 1 12 6.1a4.5 4.5 0 0 1 8.8 2.6Z" strokeLinejoin="round" />
          </svg>
          <span>{likeCount}</span>
        </button>
        <button
          type="button"
          onClick={() => setCommentsOpen((open) => !open)}
          aria-expanded={commentsOpen}
          aria-controls={`comments-${story.id}`}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-xs font-bold text-muted transition hover:bg-surface-2 hover:text-text"
        >
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.2 8.2 0 0 1-3.5-.8L4 20l1.7-3.6A7.4 7.4 0 0 1 4 11.5 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.5Z" strokeLinejoin="round" />
          </svg>
          <span>{commentCount} comments</span>
        </button>
        {likeError ? <span role="alert" className="basis-full text-xs text-danger">{likeError}</span> : null}
      </footer>

      {commentsOpen ? (
        <CommentThread
          id={`comments-${story.id}`}
          storyId={story.id}
          onClose={() => setCommentsOpen(false)}
          onCommentAdded={() => setCommentCount((count) => count + 1)}
        />
      ) : null}
    </article>
  );
}
