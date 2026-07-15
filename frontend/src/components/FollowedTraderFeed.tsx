"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import { marketHref } from "@/lib/market-href";
import { fetchSocialFeed, type SocialTradeActivity } from "@/lib/social-api";

function timeLabel(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60_000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function tradeLabel(item: SocialTradeActivity): string {
  return `${item.action.toUpperCase()} ${item.shares} ${item.outcome.toUpperCase()} · ${item.side.toUpperCase()}`;
}

function FollowedTradeCard({ item }: { item: SocialTradeActivity }) {
  return (
    <article className="rounded-xl border border-border bg-surface p-4 transition hover:border-border-light">
      <header className="flex flex-wrap items-center gap-2 text-xs">
        <Link
          href={`/traders/${encodeURIComponent(item.trader)}`}
          className="font-black text-accent-bright hover:underline"
        >
          {item.trader}
        </Link>
        <span className="rounded bg-primary-dim px-1.5 py-0.5 font-mono text-[10px] font-bold text-primary">
          {tradeLabel(item)}
        </span>
        <time className="ml-auto text-[10px] text-muted-2" dateTime={item.created_at}>
          {timeLabel(item.created_at)}
        </time>
      </header>
      <Link
        href={marketHref(item.slug)}
        className="mt-2 block font-mono text-xs text-muted hover:text-text"
      >
        {item.slug} @ {Math.round(item.price * 100)}¢
      </Link>
      <p className="mt-1 text-xs text-muted-2">Paper trade · simulated funds only</p>
    </article>
  );
}

export function FollowedTraderFeed() {
  const { token, isReady } = useAuth();
  const [items, setItems] = useState<SocialTradeActivity[] | null>(null);

  useEffect(() => {
    if (!isReady || !token) return;
    let cancelled = false;
    void fetchSocialFeed(token).then((page) => {
      if (!cancelled) setItems(page.items);
    });
    return () => {
      cancelled = true;
    };
  }, [isReady, token]);

  if (!isReady || (token && items === null)) {
    return (
      <section className="mt-4 space-y-3" aria-label="Following feed loading">
        {Array.from({ length: 4 }, (_, index) => (
          <span key={index} className="skeleton block h-20 w-full rounded-xl" />
        ))}
      </section>
    );
  }

  if (!token) {
    return (
      <section className="mt-8 rounded-xl border border-border bg-surface p-8 text-center">
        <h2 className="text-sm font-black text-text">Follow traders to build this feed</h2>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-muted">
          Log in to follow paper traders and see their recent activity in one place.
        </p>
        <Link
          href="/auth/login?next=%2Ffeed%3Fview%3Dfollowing"
          className="mt-4 inline-flex min-h-11 items-center rounded-lg bg-accent px-4 py-2 text-sm font-black text-bg transition hover:brightness-110"
        >
          Log in to follow
        </Link>
      </section>
    );
  }

  if (items?.length === 0) {
    return (
      <section className="mt-8 rounded-xl border border-border bg-surface p-8 text-center">
        <h2 className="text-sm font-black text-text">No followed-trader activity yet</h2>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-muted">
          Follow a trader from the leaderboard. Their new paper trades will appear here when available.
        </p>
        <Link
          href="/leaderboard"
          className="mt-4 inline-flex min-h-11 items-center rounded-lg bg-accent px-4 py-2 text-sm font-black text-bg transition hover:brightness-110"
        >
          Browse leaderboard
        </Link>
      </section>
    );
  }

  return (
    <section className="mt-4 space-y-3" aria-label="Followed trader activity">
      {items?.map((item) => <FollowedTradeCard key={item.order_id} item={item} />)}
    </section>
  );
}
