"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageHeader, PageShell, Panel, StatRow, StatTile } from "@/components/ui/kit";
import { useAuth } from "@/hooks/useAuth";
import {
  fetchFollowing,
  fetchTraderProfile,
  followTrader,
  unfollowTrader,
  type TraderProfile,
} from "@/lib/social-api";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function initials(value: string): string {
  const clean = value.replace(/[^a-zA-Z0-9]/g, "");
  return clean.slice(0, 2).toUpperCase() || "TR";
}

export default function TraderProfilePage() {
  const params = useParams<{ name: string }>();
  const router = useRouter();
  const { token, isReady } = useAuth();
  const name = useMemo(() => params.name ?? "", [params.name]);
  const [profile, setProfile] = useState<TraderProfile | null>(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!name || !isReady) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    void Promise.all([
      fetchTraderProfile(name),
      token ? fetchFollowing(token) : Promise.resolve([]),
    ]).then(([result, followed]) => {
      if (cancelled) return;
      setProfile(result);
      setFollowing(followed.some((entry) => entry.username === result?.username));
      if (!result) setError("That trader profile is unavailable or private.");
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [isReady, name, token]);

  async function handleFollow() {
    if (!token) {
      router.push(`/auth/login?next=${encodeURIComponent(`/traders/${name}`)}`);
      return;
    }
    setMutating(true);
    setError(null);
    try {
      const result = following
        ? await unfollowTrader(name, token)
        : await followTrader(name, token);
      setFollowing(result.following);
      setProfile((current) =>
        current ? { ...current, followers_count: result.followers_count } : current,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update that follow.");
    } finally {
      setMutating(false);
    }
  }

  if (loading) {
    return (
      <PageShell width="medium">
        <p className="text-sm text-muted">Loading trader profile…</p>
      </PageShell>
    );
  }

  if (!profile) {
    return (
      <PageShell width="medium">
        <Panel>
          <p className="text-xs font-black uppercase tracking-[0.14em] text-accent">Trader profile</p>
          <h1 className="mt-2 text-2xl font-black text-text">Profile not available</h1>
          <p className="mt-2 max-w-lg text-sm text-muted">
            {error ??
              "This profile is unknown, private, or not ranked yet. Profiles appear from the leaderboard after graded paper trades — we do not invent traders."}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link
              href="/leaderboard"
              className="inline-flex min-h-11 items-center rounded-xl bg-accent px-4 py-2 text-sm font-black text-bg transition hover:brightness-110"
            >
              Back to leaderboard
            </Link>
            <Link
              href="/markets"
              className="inline-flex min-h-11 items-center rounded-xl border border-border bg-surface px-4 py-2 text-sm font-black text-text transition hover:border-accent hover:text-accent"
            >
              Browse markets
            </Link>
          </div>
        </Panel>
      </PageShell>
    );
  }

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Trader profile"
        title={profile.username}
        subtitle={`Public paper-trading record · member since ${formatDate(profile.member_since)}`}
        actions={
          <button
            type="button"
            onClick={() => void handleFollow()}
            disabled={mutating}
            className={
              following
                ? "inline-flex min-h-11 items-center rounded-xl border border-primary/50 bg-primary-dim px-4 py-2 text-sm font-black text-primary transition hover:border-primary disabled:cursor-wait disabled:opacity-60"
                : "inline-flex min-h-11 items-center rounded-xl bg-accent px-4 py-2 text-sm font-black text-bg transition hover:brightness-110 disabled:cursor-wait disabled:opacity-60"
            }
          >
            {mutating ? "Updating…" : following ? "Unfollow" : token ? "Follow trader" : "Log in to follow"}
          </button>
        }
      />

      {error ? (
        <p role="alert" className="mb-4 rounded-xl border border-danger/30 bg-danger-dim px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-border bg-surface p-5 shadow-card">
        <header className="flex flex-wrap items-center gap-4">
          <span className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl border border-accent/35 bg-accent/10 font-mono text-xl font-black text-accent">
            {initials(profile.username)}
          </span>
          <p className="max-w-xl text-sm leading-6 text-muted">
            A transparent view of settled paper-market performance. No real-money execution is available on AlphaEdge.
          </p>
        </header>
        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Win rate" value={formatPercent(profile.win_rate)} accent />
          <StatTile label="ROI" value={formatPercent(profile.roi)} />
          <StatTile label="Settled trades" value={profile.settled_trade_count.toLocaleString()} />
          <StatTile label="Followers" value={profile.followers_count.toLocaleString()} />
        </dl>
      </section>

      <StatRow cols={2} className="mt-4">
        <StatTile label="All trades" value={profile.trade_count.toLocaleString()} hint="Paper orders recorded" />
        <StatTile label="Following" value={profile.following_count.toLocaleString()} hint="Public trader connections" />
      </StatRow>

      <p className="mt-6 text-xs text-muted-2">
        Stats are descriptive, not a guarantee of future results. Followed traders appear in your{" "}
        <Link href="/feed?view=following" className="text-accent-bright hover:underline">
          Following feed
        </Link>
        .
      </p>
    </PageShell>
  );
}
