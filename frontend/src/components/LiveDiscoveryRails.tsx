"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useMemo } from "react";
import { useLivePrice, useLivePricesMap } from "@/context/live-prices";
import { isKalshiWcMatchSlug, isLiveMirror } from "@/lib/hero-market";
import { formatCompactUSD, type Market } from "@/lib/mock-data";
import { Delta } from "./Delta";
import { RollingPrice } from "./RollingPrice";

function LiveRankRow({
  slug,
  title,
  fallback,
  showDelta = true,
  formatValue,
}: {
  slug: string;
  title: string;
  fallback: number;
  showDelta?: boolean;
  formatValue?: (price: number) => string;
}) {
  const live = useLivePrice(slug, fallback);
  const display = formatValue ? formatValue(live.price) : null;

  return (
    <Link
      href={marketHref(slug)}
      className="grid grid-cols-[26px_minmax(0,1fr)_auto] items-center gap-2.5 px-4 py-3 text-sm transition hover:bg-surface-2"
    >
      <span className="font-mono text-xs font-black text-muted-2">·</span>
      <span className="truncate font-semibold text-text">{title}</span>
      <span className="flex items-center justify-end gap-1.5">
        {display ? (
          <span className="font-mono text-sm font-black text-accent tabular">{display}</span>
        ) : (
          <RollingPrice value={live.price} flash={live.flash} className="text-sm text-accent" />
        )}
        {showDelta && <Delta value={live.deltaPts} />}
      </span>
    </Link>
  );
}

function RailShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface">
      <div className="flex items-center justify-between">
        <h2 className="px-4 pt-4 text-[12px] font-black uppercase tracking-[0.12em] text-text">
          {title}
        </h2>
        <Link
          href="/markets"
          className="mr-4 mt-4 text-xs font-black text-muted transition hover:text-accent"
        >
          See all
        </Link>
      </div>
      <ol className="mt-3 divide-y divide-border">{children}</ol>
    </section>
  );
}

function preferKalshiMatches(markets: Market[]): Market[] {
  const wc = markets.filter((m) => isKalshiWcMatchSlug(m.slug));
  if (wc.length) return wc;
  const live = markets.filter((m) => isLiveMirror(m));
  return live.length ? live : markets;
}

export function LiveTrendingRail({ markets }: { markets: Market[] }) {
  const pool = preferKalshiMatches(markets);
  const rows = useMemo(
    () =>
      [...pool]
        .sort((a, b) => b.volume - a.volume)
        .slice(0, 6),
    [pool],
  );

  return (
    <RailShell title="Trending">
      {rows.map((m, i) => (
        <li key={m.slug}>
          <div className="grid grid-cols-[26px_minmax(0,1fr)] items-center">
            <span className="pl-4 font-mono text-xs font-black text-muted-2">{i + 1}</span>
            <LiveRankRow
              slug={m.slug}
              title={m.title}
              fallback={m.outcomes[0]?.price ?? 0.5}
            />
          </div>
        </li>
      ))}
    </RailShell>
  );
}

export function LiveTopMoversRail({ markets }: { markets: Market[] }) {
  const prices = useLivePricesMap();
  const pool = preferKalshiMatches(markets);

  const rows = useMemo(() => {
    return [...pool]
      .map((m) => ({
        m,
        delta: prices[m.slug]?.deltaPts ?? 0,
      }))
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
      .slice(0, 5);
  }, [pool, prices]);

  return (
    <RailShell title="Top movers">
      {rows.map(({ m }, i) => (
        <li key={m.slug}>
          <div className="grid grid-cols-[26px_minmax(0,1fr)] items-center">
            <span className="pl-4 font-mono text-xs font-black text-muted-2">{i + 1}</span>
            <LiveRankRow
              slug={m.slug}
              title={m.title}
              fallback={m.outcomes[0]?.price ?? 0.5}
            />
          </div>
        </li>
      ))}
    </RailShell>
  );
}

export function LiveNewRail({ markets }: { markets: Market[] }) {
  const live = markets.filter((m) => isLiveMirror(m));
  const pool = live.length ? live : markets;
  const rows = useMemo(
    () =>
      [...pool]
        .sort((a, b) => Date.parse(b.endsAt) - Date.parse(a.endsAt))
        .slice(0, 5),
    [pool],
  );

  return (
    <RailShell title="New">
      {rows.map((m, i) => (
        <li key={m.slug}>
          <div className="grid grid-cols-[26px_minmax(0,1fr)] items-center">
            <span className="pl-4 font-mono text-xs font-black text-muted-2">{i + 1}</span>
            <LiveRankRow
              slug={m.slug}
              title={m.title}
              fallback={m.outcomes[0]?.price ?? 0.5}
              showDelta={false}
            />
          </div>
        </li>
      ))}
    </RailShell>
  );
}

export function LiveVolumeRail({ markets }: { markets: Market[] }) {
  const live = markets.filter((m) => isLiveMirror(m));
  const pool = live.length ? live : markets;
  const rows = useMemo(
    () => [...pool].sort((a, b) => b.volume - a.volume).slice(0, 6),
    [pool],
  );

  return (
    <RailShell title="Highest volume">
      {rows.map((m, i) => (
        <li key={m.slug}>
          <div className="grid grid-cols-[26px_minmax(0,1fr)] items-center">
            <span className="pl-4 font-mono text-xs font-black text-muted-2">{i + 1}</span>
            <LiveRankRow
              slug={m.slug}
              title={m.title}
              fallback={m.outcomes[0]?.price ?? 0.5}
              showDelta={false}
              formatValue={() => formatCompactUSD(m.volume)}
            />
          </div>
        </li>
      ))}
    </RailShell>
  );
}
