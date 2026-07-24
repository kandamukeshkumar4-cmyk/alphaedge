"use client";

import Link from "next/link";
import { FormEvent, useEffect, useId, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import {
  addComment,
  isSocialApiError,
  listComments,
  type Comment,
} from "@/lib/social-api";

type CommentThreadProps = {
  id: string;
  storyId: string;
  onClose: () => void;
  onCommentAdded: () => void;
};

function relativeTime(timestamp: string): string {
  const then = Date.parse(timestamp);
  if (!Number.isFinite(then)) return "Time unavailable";
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function CommentAvatar({ comment }: { comment: Comment }) {
  const initials = comment.actor.display_name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return comment.actor.avatar_url ? (
    <span className="grid h-7 w-7 shrink-0 overflow-hidden rounded-full border border-border bg-surface-3">
      {/* eslint-disable-next-line @next/next/no-img-element -- public avatar contract; static export has no optimizer. */}
      <img
        src={comment.actor.avatar_url}
        alt={`${comment.actor.display_name} avatar`}
        width={28}
        height={28}
        loading="lazy"
        className="h-full w-full object-cover"
      />
    </span>
  ) : (
    <span aria-hidden="true" className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface-3 font-mono text-[9px] font-bold text-muted">
      {initials}
    </span>
  );
}

export function CommentThread({ id, storyId, onClose, onCommentAdded }: CommentThreadProps) {
  const { token, isReady } = useAuth();
  const fieldId = useId();
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const canComment = isReady && Boolean(token);

  useEffect(() => {
    let cancelled = false;
    setComments(null);
    setLoadError(null);
    void listComments(storyId).then(
      ({ data }) => {
        if (!cancelled) setComments(data.items);
      },
      () => {
        if (!cancelled) {
          setComments([]);
          setLoadError("Comments are unavailable right now.");
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [storyId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canComment || !token || submitting) return;
    setSubmitError(null);
    setSubmitting(true);
    try {
      const result = await addComment(token, storyId, body);
      setComments((current) => [...(current ?? []), result.data]);
      setBody("");
      onCommentAdded();
    } catch (error) {
      if (isSocialApiError(error) && error.status === 422) {
        setSubmitError(error.message || "Comment must be between 1 and 500 characters.");
      } else {
        setSubmitError("Comment could not be posted. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section id={id} aria-label="Comments" className="mt-4 border-t border-border/70 pt-4">
      <header className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-bold uppercase tracking-[0.12em] text-muted">Discussion</h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close comments"
          className="min-h-11 rounded-lg px-3 text-xs font-bold text-muted transition hover:bg-surface-2 hover:text-text"
        >
          Close
        </button>
      </header>

      {loadError ? (
        <p role="alert" className="mt-3 rounded-lg border border-danger/30 bg-danger-dim px-3 py-2 text-xs text-danger">
          {loadError}
        </p>
      ) : comments === null ? (
        <p className="mt-3 rounded-lg border border-border bg-bg/50 px-3 py-3 text-xs text-muted" aria-live="polite">
          Loading comments…
        </p>
      ) : comments.length === 0 ? (
        <p className="mt-3 rounded-lg border border-border bg-bg/50 px-3 py-3 text-xs text-muted">
          No comments yet. Start the discussion.
        </p>
      ) : (
        <ul className="mt-3 space-y-3" aria-label="Story comments">
          {comments.map((comment) => (
            <li key={comment.id} className="flex items-start gap-2.5">
              <CommentAvatar comment={comment} />
              <p className="min-w-0 flex-1 rounded-xl border border-border bg-bg/50 px-3 py-2">
                <span className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-xs font-bold text-text">{comment.actor.display_name}</span>
                  <time dateTime={comment.created_at} className="text-[10px] text-muted-2">
                    {relativeTime(comment.created_at)}
                  </time>
                </span>
                <span className="mt-1 block whitespace-pre-wrap break-words text-sm leading-relaxed text-muted">
                  {comment.body}
                </span>
              </p>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={(event) => void submit(event)} className="mt-4 rounded-xl border border-border bg-bg/40 p-3">
        <label htmlFor={fieldId} className="text-xs font-bold text-text">Add a comment</label>
        <textarea
          id={fieldId}
          value={body}
          onChange={(event) => setBody(event.target.value.slice(0, 500))}
          maxLength={500}
          disabled={!canComment || submitting}
          aria-describedby={`${fieldId}-counter ${fieldId}-hint`}
          placeholder={canComment ? "Share context with the desk" : "Sign in to comment"}
          className="mt-2 min-h-24 w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 text-sm leading-relaxed text-text outline-none transition placeholder:text-muted-2 focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <p id={`${fieldId}-counter`} className="mt-1 text-right font-mono text-[10px] text-muted-2">
          {body.length}/500
        </p>
        {!canComment ? (
          <p id={`${fieldId}-hint`} className="mt-2 text-xs text-muted">
            <Link href={`/auth/login?next=${encodeURIComponent("/community")}`} className="font-bold text-accent-bright hover:underline">
              Sign in to comment
            </Link>
          </p>
        ) : (
          <p id={`${fieldId}-hint`} className="mt-2 flex items-center justify-between gap-3">
            <span className="text-xs text-muted">Keep it useful and paper-market focused.</span>
            <button
              type="submit"
              disabled={submitting || body.trim().length === 0}
              className="min-h-10 shrink-0 rounded-lg bg-primary px-3 text-xs font-bold text-bg transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Posting…" : "Post comment"}
            </button>
          </p>
        )}
        {submitError ? (
          <p role="alert" className="mt-2 text-xs text-danger">{submitError}</p>
        ) : null}
      </form>
    </section>
  );
}
