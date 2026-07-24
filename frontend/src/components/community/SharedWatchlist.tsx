"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getSharedWatchlist, type SharedWatchlist } from "@/lib/social-api";

function addedLabel(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

export function SharedWatchlist({ handle }: { handle: string }) {
  const [watchlist, setWatchlist] = useState<SharedWatchlist | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setWatchlist(null);
    setError(null);
    void getSharedWatchlist(handle).then(
      ({ data }) => {
        if (!cancelled) setWatchlist(data);
      },
      () => {
        if (!cancelled) {
          setWatchlist({ handle, display_name: handle, items: [] });
          setError("This shared watchlist is unavailable right now.");
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [handle]);

  return (
    <main className="min-h-screen bg-bg">
      <section className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
        {watchlist === null ? (
          <section aria-label="Loading shared watchlist" className="rounded-2xl border border-border bg-surface p-5">
            <span className="block h-4 w-36 animate-pulse rounded bg-surface-3" />
            <span className="mt-3 block h-8 w-64 animate-pulse rounded bg-surface-3" />
            <span className="mt-8 block h-16 w-full animate-pulse rounded-xl bg-surface-3" />
          </section>
        ) : (
          <>
            <header className="mb-6">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
                Shared watchlist
              </p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-text">{watchlist.display_name}</h1>
              <p className="mt-1 text-sm text-muted">@{watchlist.handle} · public paper-market research</p>
            </header>

            {error ? (
              <p role="alert" className="mb-4 rounded-xl border border-danger/30 bg-danger-dim px-4 py-3 text-sm text-danger">
                {error}
              </p>
            ) : null}

            {watchlist.items.length === 0 ? (
              <section className="rounded-2xl border border-border bg-surface px-6 py-12 text-center">
                <p className="text-base font-black text-text">No shared markets yet</p>
                <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted">
                  This watchlist is public, but its owner has not shared any markets.
                </p>
              </section>
            ) : (
              <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
                <ul className="divide-y divide-border/70" aria-label={`${watchlist.display_name} shared markets`}>
                  {watchlist.items.map((item) => (
                    <li key={`${item.market_slug}-${item.added_at}`} className="py-3 first:pt-0 last:pb-0">
                      <Link
                        href={`/markets/${encodeURIComponent(item.market_slug)}`}
                        className="flex min-h-11 items-center justify-between gap-4 rounded-lg px-2 py-1 transition hover:bg-surface-2"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-bold text-text">{item.market_title}</span>
                          <span className="mt-1 block truncate font-mono text-[10px] text-muted-2">{item.market_slug}</span>
                        </span>
                        <span className="shrink-0 text-right text-[10px] text-muted-2">Added {addedLabel(item.added_at)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}
