"use client";

// W01 — Watchlist page. Lists the caller's tracked markets (JWT-scoped, backend
// J01) with model edge + last-move. Honest empties: "sign in to track markets"
// when anon, "no markets yet" when signed in with none. Research only, paper
// trading only — bookmarks never place orders.
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader, PageShell } from "@/components/ui/kit";
import { WatchlistAlerts } from "@/components/WatchlistAlerts";
import { WatchlistStar } from "@/components/WatchlistStar";
import { useAuth } from "@/hooks/useAuth";
import { useWatchlist } from "@/hooks/useWatchlist";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";
import {
  buildWatchlistView,
  fetchWatchlist,
  type WatchlistEntry,
} from "@/lib/watchlist-api";

const TONE_CLASS: Record<"up" | "down" | "neutral", string> = {
  up: "text-primary",
  down: "text-danger",
  neutral: "text-muted",
};

export default function WatchlistPage() {
  const { token, isReady } = useAuth();
  const { slugs } = useWatchlist();
  const [entries, setEntries] = useState<WatchlistEntry[] | null>(null);

  useEffect(() => {
    if (!isReady) return;
    if (!token) {
      setEntries([]);
      return;
    }
    let dead = false;
    void fetchWatchlist(token).then((data) => {
      if (!dead) setEntries(data);
    });
    return () => {
      dead = true;
    };
  }, [isReady, token]);

  // Optimistic removals: hide rows no longer in the shared watched set.
  const rows = buildWatchlistView(entries ? { items: entries } : null).filter((r) =>
    slugs.includes(r.slug),
  );

  const loading = !isReady || entries === null;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Tracking"
        title="Watchlist"
        subtitle="Markets you track, with the model's edge and last move. Research only — paper trading, simulated funds. Bookmarks never place orders."
      />

      {loading ? (
        <ListSkeleton />
      ) : !token ? (
        <EmptyState
          title="Sign in to track markets"
          body="Your watchlist is saved to your account. Sign in, then tap the ☆ on any market to start tracking it."
          cta={{ href: "/auth/login?next=/watchlist", label: "Sign in" }}
        />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No markets yet"
          body="Tap the ☆ on any market card or detail page and it lands here with its live edge and last move."
          cta={{ href: "/markets", label: "Browse markets" }}
        />
      ) : (
        <ul className="space-y-2" aria-label="Tracked markets">
          {rows.map((row) => (
            <li
              key={row.slug}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface px-3 py-3"
            >
              <WatchlistStar slug={row.slug} size="sm" />
              <Link href={marketHref(row.slug)} className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-text hover:text-accent-bright">
                  {row.title}
                </p>
                <p className="truncate font-mono text-[11px] text-muted-2">{row.slug}</p>
              </Link>
              <div className="shrink-0 text-right">
                <p className="font-mono text-sm font-semibold tabular-nums text-text">
                  {row.yesPriceLabel}
                </p>
                <p className="text-[10px] uppercase tracking-wide text-muted-2">YES</p>
              </div>
              <div className="hidden w-20 shrink-0 text-right sm:block">
                <p className={cn("font-mono text-xs font-semibold", TONE_CLASS[row.edgeTone])}>
                  {row.edgeLabel ?? "—"}
                </p>
                <p className="text-[10px] uppercase tracking-wide text-muted-2">Edge</p>
              </div>
              <div className="w-20 shrink-0 text-right">
                <p className={cn("font-mono text-xs font-semibold", TONE_CLASS[row.lastMoveTone])}>
                  {row.lastMoveLabel ?? "—"}
                </p>
                <p className="text-[10px] uppercase tracking-wide text-muted-2">Last move</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {token && rows.length > 0 ? <WatchlistAlerts token={token} /> : null}
    </PageShell>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-border bg-surface px-3 py-3">
          <div className="skeleton h-7 w-7 rounded-lg" />
          <div className="min-w-0 flex-1">
            <div className="skeleton h-4 w-2/3 rounded" />
            <div className="skeleton mt-1.5 h-3 w-1/3 rounded" />
          </div>
          <div className="skeleton h-8 w-12 rounded" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  title,
  body,
  cta,
}: {
  title: string;
  body: string;
  cta: { href: string; label: string };
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-8 text-center">
      <p className="text-sm font-semibold text-text">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">{body}</p>
      <Link
        href={cta.href}
        className="mt-4 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
      >
        {cta.label}
      </Link>
    </div>
  );
}
