"use client";

/**
 * TraderProfileCard — U13 "Your trading profile" card.
 *
 * Renders the deterministic profile derived from the user's own paper-trade
 * history. Numbers come from GET /api/v1/profile — never fabricated.
 *
 * Empty state: shown for new users with fewer than min_trades_required trades.
 * Explains what will appear once they start trading.
 *
 * Privacy banner: "Derived only from your paper activity in this app."
 * This is part of the product — never hidden.
 *
 * GUARDRAIL: This component is read-only display. No order surfaces here.
 */

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchTraderProfile, type TraderProfile } from "@/lib/portfolio-api";

type Props = {
  token: string;
};

function WinRateBadge({ rate }: { rate: number }) {
  if (rate < 0) {
    return <span className="text-xs text-muted">no settled trades yet</span>;
  }
  const pct = Math.round(rate * 100);
  const tone =
    pct >= 55 ? "text-green-400" : pct >= 45 ? "text-yellow-400" : "text-red-400";
  return <span className={cn("text-xs font-bold", tone)}>{pct}%</span>;
}

function StreakNote({ streak }: { streak: number }) {
  if (streak === 0) return null;
  const abs = Math.abs(streak);
  if (streak > 0) {
    return (
      <span className="rounded bg-green-900/30 px-1.5 py-0.5 text-xs font-medium text-green-400">
        {abs}-trade win streak
      </span>
    );
  }
  return (
    <span className="rounded bg-red-900/30 px-1.5 py-0.5 text-xs font-medium text-red-400">
      {abs}-trade losing streak
    </span>
  );
}

function TiltNote({
  sizesUp,
  multiplier,
}: {
  sizesUp: boolean;
  multiplier: number;
}) {
  if (!sizesUp) return null;
  return (
    <span className="rounded bg-orange-900/30 px-1.5 py-0.5 text-xs font-medium text-orange-400">
      sizes up {multiplier.toFixed(1)}x after losses
    </span>
  );
}

export function TraderProfileCard({ token }: Props) {
  const [profile, setProfile] = useState<TraderProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchTraderProfile(token)
      .then((result) => setProfile(result))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">
          Your Trading Profile
        </p>
        <div className="mt-3 space-y-2">
          <div className="skeleton h-4 w-3/4 rounded" />
          <div className="skeleton h-4 w-1/2 rounded" />
          <div className="skeleton h-4 w-2/3 rounded" />
        </div>
      </section>
    );
  }

  if (!profile) {
    return null;
  }

  // ── Empty state for new users ──
  if (!profile.has_data) {
    return (
      <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">
            Your Trading Profile
          </p>
          <span className="rounded-full bg-surface px-2 py-0.5 text-[10px] font-medium text-muted ring-1 ring-border">
            provisional
          </span>
        </div>
        <p className="mt-3 text-sm text-muted">
          {profile.empty_state_message}
        </p>
        <p className="mt-4 rounded-xl border border-border bg-bg px-3 py-2 text-[11px] text-muted">
          {profile.source_note}
        </p>
      </section>
    );
  }

  // ── Full profile ──
  return (
    <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">
          Your Trading Profile
        </p>
        <div className="flex flex-wrap gap-1.5">
          {profile.current_streak !== 0 && (
            <StreakNote streak={profile.current_streak} />
          )}
          {profile.sizes_up_after_losses && (
            <TiltNote
              sizesUp={profile.sizes_up_after_losses}
              multiplier={profile.tilt_multiplier}
            />
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {/* Favourite categories */}
        <div className="rounded-xl border border-border bg-bg p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Favourite categories
          </p>
          {profile.favorite_categories.length > 0 ? (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {profile.favorite_categories.map((cat) => (
                <span
                  key={cat}
                  className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
                >
                  {cat}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-xs text-muted">no data yet</p>
          )}
        </div>

        {/* Typical size */}
        <div className="rounded-xl border border-border bg-bg p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Typical position size
          </p>
          <p className="mt-1 text-sm font-bold text-text">
            ${profile.avg_cost_usd.toFixed(2)}
            <span className="ml-1 text-xs font-normal text-muted">
              ({profile.avg_size_pct_bankroll.toFixed(1)}% of bankroll)
            </span>
          </p>
        </div>

        {/* Avg hold time */}
        <div className="rounded-xl border border-border bg-bg p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Avg hold time
          </p>
          <p className="mt-1 text-sm font-bold text-text">
            {profile.avg_hold_hours > 0
              ? profile.avg_hold_hours < 1
                ? `${Math.round(profile.avg_hold_hours * 60)}m`
                : profile.avg_hold_hours < 24
                ? `${profile.avg_hold_hours.toFixed(1)}h`
                : `${(profile.avg_hold_hours / 24).toFixed(1)}d`
              : "—"}
          </p>
        </div>
      </div>

      {/* Win rate by category */}
      {profile.category_stats.length > 0 && (
        <div className="mt-3 rounded-xl border border-border bg-bg p-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
            Win rate by category
          </p>
          <div className="space-y-1.5">
            {profile.category_stats.slice(0, 4).map((cs) => (
              <div
                key={cs.category}
                className="flex items-center justify-between gap-2 text-xs"
              >
                <span className="font-medium text-text">{cs.category}</span>
                <div className="flex items-center gap-2 text-muted">
                  <span>{cs.trade_count} trades</span>
                  <WinRateBadge rate={cs.win_rate} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Entry style */}
      {profile.entry_style && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-muted">
          <span className="font-semibold text-text">Entry style:</span>
          <span>{profile.entry_style}</span>
        </div>
      )}

      {/* Overall win rate */}
      {profile.overall_win_rate >= 0 && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-muted">
          <span className="font-semibold text-text">Overall win rate:</span>
          <WinRateBadge rate={profile.overall_win_rate} />
        </div>
      )}

      {/* Privacy / source note — always shown */}
      <p className="mt-4 rounded-xl border border-border bg-bg px-3 py-2 text-[11px] text-muted">
        {profile.source_note}
      </p>
    </section>
  );
}
