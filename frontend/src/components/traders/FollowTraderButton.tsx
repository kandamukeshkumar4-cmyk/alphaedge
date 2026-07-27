"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import {
  fetchFollowing,
  followTrader,
  unfollowTrader,
} from "@/lib/social-api";

/**
 * Follow / unfollow control for a public paper trader.
 *
 * Regression restore: the pre-loop104 trader page carried this control in its
 * header. loop104 rewrote `/traders/[name]` around `TraderDetail` and dropped
 * it, leaving `POST|DELETE /api/v1/social/follow/{trader}` reachable only by
 * API — so the follow half of the social journey (e2e/social.spec.ts) had no
 * UI at all. Behaviour matches the original: logged-out visitors see a prompt,
 * the label flips to "Unfollow" once followed, and the live follower count
 * from the mutation response is handed back to the page.
 */
export function FollowTraderButton({
  trader,
  onFollowersChange,
}: {
  trader: string;
  onFollowersChange?: (followersCount: number) => void;
}) {
  const { token, isReady } = useAuth();
  const [following, setFollowing] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setFollowing(false);
      return;
    }
    void fetchFollowing(token).then((entries) => {
      if (cancelled) return;
      setFollowing(
        entries.some(
          (entry) => entry.username.toLowerCase() === trader.toLowerCase(),
        ),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [token, trader]);

  const toggle = useCallback(async () => {
    if (!token || mutating) return;
    setMutating(true);
    setError(null);
    try {
      const result = following
        ? await unfollowTrader(trader, token)
        : await followTrader(trader, token);
      setFollowing(result.following);
      onFollowersChange?.(result.followers_count);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not update follow.",
      );
    } finally {
      setMutating(false);
    }
  }, [following, mutating, onFollowersChange, token, trader]);

  // Signed-out visitors get no social control at all: the trader page is an
  // evidence file for them (e2e/traders.spec.ts asserts a follow-free page),
  // and a disabled "Log in to follow" button would be noise on a read-only
  // surface. Following requires an account, so the control requires a session.
  if (!isReady || !token) return null;

  const label = mutating ? "Updating…" : following ? "Unfollow" : "Follow trader";

  return (
    <span className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => void toggle()}
        disabled={mutating}
        aria-pressed={following}
        className={
          following
            ? "inline-flex min-h-11 items-center rounded-xl border border-primary/50 bg-primary-dim px-4 py-2 text-sm font-black text-primary outline-none transition hover:border-primary focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-wait disabled:opacity-60"
            : "inline-flex min-h-11 items-center rounded-xl bg-accent px-4 py-2 text-sm font-black text-bg outline-none transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60"
        }
      >
        {label}
      </button>
      {error ? (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      ) : null}
    </span>
  );
}
