"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PageHeader, PageShell, Panel, StatRow, StatTile } from "@/components/ui/kit";
import { FollowTraderButton } from "@/components/traders/FollowTraderButton";
import { fetchTraderDetail, type TraderDetail as TraderDetailData } from "@/lib/traders-api";

const currency = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
  signDisplay: "exceptZero",
});

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function DetailSkeleton() {
  return (
    <PageShell width="medium">
      <section
        className="h-28 animate-pulse rounded-2xl border border-border bg-surface"
        aria-label="Loading trader detail"
        data-testid="trader-detail-loading"
      />
      <section className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-hidden>
        {Array.from({ length: 4 }, (_, index) => (
          <span key={index} className="h-24 animate-pulse rounded-xl bg-surface-2" />
        ))}
      </section>
    </PageShell>
  );
}

export function TraderDetail({ name }: { name: string }) {
  const [data, setData] = useState<TraderDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  // Live follower count returned by the follow/unfollow mutation, so the
  // track-record tile reflects the click without a full refetch.
  const [followersOverride, setFollowersOverride] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setMissing(false);
    setFollowersOverride(null);
    try {
      const result = await fetchTraderDetail(name);
      setData(result);
      setMissing(result === null);
    } catch (cause) {
      setData(null);
      setError(
        cause instanceof Error
          ? cause.message
          : "The live trader record could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [name]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  if (loading) return <DetailSkeleton />;

  if (error || missing || !data) {
    return (
      <PageShell width="medium">
        <Panel>
          <span className="font-mono text-xs font-black uppercase tracking-[0.12em] text-muted-2">
            Public paper record
          </span>
          <h1 className="mt-3 text-2xl font-black text-text">
            {error ? "Trader data unavailable" : "Profile not available"}
          </h1>
          {/* The API cannot tell "unknown name" apart from "trader opted out of
              a public profile" — both return no record. Say exactly that
              instead of asserting the name does not exist. */}
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted" role={error ? "alert" : undefined}>
            {error ??
              "This profile is unavailable or private: the name is unknown to the live ranking and public directory, or the trader opted out of a public profile. No substitute profile is shown."}
          </p>
          <span className="mt-5 flex flex-wrap gap-2">
            {error ? (
              <button
                type="button"
                onClick={() => setReloadKey((value) => value + 1)}
                className="min-h-11 rounded-xl bg-primary px-4 py-2 text-sm font-black text-bg outline-none transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-primary"
              >
                Retry live record
              </button>
            ) : null}
            <Link
              href="/traders"
              className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
            >
              Back to traders
            </Link>
          </span>
        </Panel>
      </PageShell>
    );
  }

  const entry = data.leaderboard;
  const profile = data.profile;
  const displayName = profile?.username ?? entry?.username ?? name;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Trader evidence file"
        title={displayName}
        subtitle={
          profile
            ? `Public paper trader · member since ${formatDate(profile.member_since)}`
            : "Ranked paper-trading record"
        }
        actions={
          <span className="flex flex-wrap items-center gap-2">
            <Link
              href="/traders"
              className="inline-flex min-h-11 items-center rounded-xl border border-border bg-surface px-4 py-2 text-sm font-black text-text outline-none transition hover:border-primary hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
            >
              All traders
            </Link>
            {profile ? (
              <FollowTraderButton
                trader={displayName}
                onFollowersChange={setFollowersOverride}
              />
            ) : null}
          </span>
        }
      />

      {data.partial ? (
        <p
          className="mb-4 rounded-xl border border-gold/30 bg-gold/10 px-4 py-3 text-sm text-text"
          role="status"
        >
          One live source did not return a matching record. Available evidence is shown
          without filling the gap.
        </p>
      ) : null}

      <Panel className="overflow-hidden" padded={false}>
        <section className="grid gap-0 lg:grid-cols-[220px_1fr]">
          <header className="flex min-h-[210px] flex-col justify-between border-b border-border bg-primary-dim/50 p-5 lg:border-b-0 lg:border-r">
            <span className="text-[11px] font-black uppercase tracking-[0.13em] text-primary">
              Realized P&amp;L rank
            </span>
            <span
              className="font-mono text-6xl font-black tracking-tighter text-primary"
              data-testid="trader-detail-rank"
            >
              {entry ? `#${entry.rank}` : "—"}
            </span>
            <span className="text-xs leading-5 text-muted">
              {entry
                ? "Position among traders with settled paper outcomes."
                : "No matching top-100 P&L rank returned."}
            </span>
          </header>

          <section className="p-5 sm:p-6">
            <span className="font-mono text-[11px] font-black uppercase tracking-[0.12em] text-muted-2">
              Why this position
            </span>
            <h2 className="mt-2 text-xl font-black text-text">
              {entry
                ? `${currency.format(entry.realized_pnl)} in realized paper P&L`
                : "Public profile evidence"}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              {entry
                ? `Rank ${entry.rank} comes from settled paper gains minus settled paper losses. Open positions do not affect this order. The record also shows ${formatPercent(entry.roi)} return on paper capital and a ${formatPercent(entry.win_rate)} settled win rate across ${entry.total_trades.toLocaleString()} recorded trades.`
                : "The public profile exists, but the live realized-P&L page did not include this trader. AlphaEdge does not infer a missing rank."}
            </p>
          </section>
        </section>
      </Panel>

      <StatRow className="mt-4">
        <StatTile
          label="Realized paper P&L"
          value={entry ? currency.format(entry.realized_pnl) : "—"}
          accent
        />
        <StatTile
          label="ROI"
          value={entry ? formatPercent(entry.roi) : profile ? formatPercent(profile.roi) : "—"}
          hint="On paper capital"
        />
        <StatTile
          label="Settled win rate"
          value={
            entry
              ? formatPercent(entry.win_rate)
              : profile
                ? formatPercent(profile.win_rate)
                : "—"
          }
        />
        <StatTile
          label="Settled trades"
          value={profile ? profile.settled_trade_count.toLocaleString() : "—"}
        />
      </StatRow>

      <Panel className="mt-4" title="Public track record">
        {profile ? (
          <dl className="grid gap-4 sm:grid-cols-3">
            <span>
              <dt className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-2">
                All paper trades
              </dt>
              <dd className="mt-1 font-mono text-lg font-black tabular-nums text-text">
                {profile.trade_count.toLocaleString()}
              </dd>
            </span>
            <span>
              <dt className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-2">
                Followers
              </dt>
              <dd className="mt-1 font-mono text-lg font-black tabular-nums text-text">
                {(followersOverride ?? profile.followers_count).toLocaleString()}
              </dd>
            </span>
            <span>
              <dt className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-2">
                Following
              </dt>
              <dd className="mt-1 font-mono text-lg font-black tabular-nums text-text">
                {profile.following_count.toLocaleString()}
              </dd>
            </span>
          </dl>
        ) : (
          <p className="text-sm text-muted">
            The live social profile did not return public details for this ranked name.
          </p>
        )}
      </Panel>

      <p className="mt-5 text-xs leading-5 text-muted-2">
        Historical paper performance is descriptive, not a recommendation or a guarantee.
        This page cannot place, size, or execute an order.
      </p>
    </PageShell>
  );
}
