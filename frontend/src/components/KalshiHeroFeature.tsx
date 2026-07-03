"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { HeroFeature } from "./HeroFeature";
import { MultiLineChart } from "./MultiLineChart";
import { RollingPrice } from "./RollingPrice";
import { useLivePrice } from "@/context/live-prices";
import { fetchLatestPrice } from "@/lib/alphaedge-api";
import { flagForTeam } from "@/lib/team-flags";
import { isLiveMirror } from "@/lib/hero-market";
import { formatVolUsd, payoutMultiplier, resolveOutcomeSlug } from "@/lib/live-price";
import { type Market, type MarketOutcome } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

function sortMatchOutcomes(outcomes: MarketOutcome[]): MarketOutcome[] {
  return [...outcomes].sort((a, b) => {
    const aTie = /tie|draw/i.test(a.label);
    const bTie = /tie|draw/i.test(b.label);
    if (aTie && !bTie) return -1;
    if (bTie && !aTie) return 1;
    return b.price - a.price;
  });
}

function HeroLiveStatus({ slugs }: { slugs: string[] }) {
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [source, setSource] = useState<string>("api");
  const [nowMs, setNowMs] = useState(0);

  useEffect(() => {
    const tick = () => setNowMs(Date.now());
    tick();
    const tickId = setInterval(tick, 1000);
    return () => clearInterval(tickId);
  }, []);

  useEffect(() => {
    let dead = false;
    const poll = async () => {
      for (const slug of slugs) {
        const latest = await fetchLatestPrice(slug);
        if (dead || !latest?.ts) continue;
        setUpdatedAt(latest.ts);
        setSource(latest.source);
        break;
      }
    };
    void poll();
    const id = setInterval(() => void poll(), 3000);
    return () => {
      dead = true;
      clearInterval(id);
    };
  }, [slugs]);

  const ago =
    updatedAt != null && nowMs > 0
      ? `${Math.max(0, Math.round((nowMs - Date.parse(updatedAt)) / 1000))}s ago`
      : "syncing…";

  return (
    <div className="mt-5 border-t border-white/10 pt-4 text-xs text-white/50">
      <div className="font-bold uppercase tracking-wider text-white/35">Data feed</div>
      <p className="mt-2 leading-relaxed">
        Prices and chart ticks from the AlphaEdge API mirroring Kalshi contracts. Paper trading
        only — not hardcoded.
      </p>
      <p className="mt-2 font-mono text-[11px] text-[#05b169]">
        Last snapshot: {ago} · source={source}
      </p>
    </div>
  );
}

function OutcomeRow({
  outcome,
  market,
  isFavorite,
}: {
  outcome: MarketOutcome;
  market: Market;
  isFavorite: boolean;
}) {
  const slug = resolveOutcomeSlug(outcome.id, market.slug);
  const tick = useLivePrice(slug, outcome.price);
  const payout = payoutMultiplier(tick.price);
  const isTie = /tie|draw/i.test(outcome.label);

  return (
    <tr className="group border-b border-border/80 last:border-0">
      <td className="py-3 pr-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="text-xl leading-none">{flagForTeam(outcome.label)}</span>
          <span className="truncate text-[15px] font-semibold text-text">{outcome.label}</span>
        </div>
      </td>
      <td className="py-3 pr-3 text-right font-mono text-sm font-semibold tabular text-muted">
        {payout}
      </td>
      <td className="py-3 text-right">
        <span
          className={cn(
            "inline-flex min-w-[52px] justify-center rounded-md border px-2.5 py-1 font-mono text-sm font-bold tabular",
            isFavorite && !isTie
              ? "border-primary/60 bg-primary/10 text-primary"
              : isTie
                ? "border-border-light bg-surface-2 text-muted"
                : "border-accent/50 bg-accent/10 text-accent",
          )}
        >
          <RollingPrice value={tick.price} cents flash={tick.flash} className="text-sm" />
        </span>
      </td>
    </tr>
  );
}

function KalshiHeroPanel({ markets }: { markets: Market[] }) {
  const [idx, setIdx] = useState(0);
  const market = markets[idx] ?? markets[0];

  const count = markets.length;
  const outcomes = sortMatchOutcomes(market?.outcomes.slice(0, 4) ?? []);
  const firstSlug =
    (resolveOutcomeSlug(outcomes[0]?.id ?? "", market?.slug ?? "") || market?.slug) ?? "";

  const favoriteIdx = outcomes.reduce(
    (best, o, i) => (o.price > outcomes[best].price ? i : best),
    0,
  );

  const newsBlurb = useMemo(() => market.description?.slice(0, 220) || "", [market]);

  const outcomeSlugs = useMemo(
    () => outcomes.map((o) => resolveOutcomeSlug(o.id, market.slug)),
    [outcomes, market.slug],
  );

  if (!market) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-white/10 bg-[#0a0a0a]">
      <div className="grid lg:grid-cols-[minmax(340px,420px)_minmax(0,1fr)]">
        <div className="border-b border-border p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted">
              <span>⚽</span>
              <span>Soccer</span>
            </div>
            {count > 1 && (
              <div className="flex items-center gap-2 text-sm text-muted">
                <button
                  type="button"
                  aria-label="Previous match"
                  onClick={() => setIdx((p) => (p - 1 + count) % count)}
                  className="text-muted transition hover:text-text"
                >
                  ‹
                </button>
                <span className="font-mono tabular">
                  {idx + 1} of {count}
                </span>
                <button
                  type="button"
                  aria-label="Next match"
                  onClick={() => setIdx((p) => (p + 1) % count)}
                  className="text-muted transition hover:text-text"
                >
                  ›
                </button>
              </div>
            )}
          </div>

          <Link
            href={marketHref(firstSlug)}
            className="mt-3 block text-[26px] font-bold leading-tight tracking-tight text-text hover:text-white"
          >
            {market.title}
          </Link>

          <table className="mt-5 w-full text-left">
            <thead>
              <tr className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
                <th className="pb-2 font-semibold">Market</th>
                <th className="pb-2 text-right font-semibold">Pays out</th>
                <th className="pb-2 text-right font-semibold">Odds</th>
              </tr>
            </thead>
            <tbody>
              {outcomes.map((outcome, i) => (
                <OutcomeRow
                  key={outcome.id}
                  outcome={outcome}
                  market={market}
                  isFavorite={i === favoriteIdx}
                />
              ))}
            </tbody>
          </table>

          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
            <span className="font-mono font-semibold tabular text-text">
              {formatVolUsd(market.volume)} vol
            </span>
            <span className="text-muted-2">·</span>
            <span className="text-muted">Kalshi mirror · Moneyline</span>
            <span className="text-muted-2">·</span>
            <span className="text-muted">{market.marketCount ?? outcomes.length} contracts</span>
          </div>

          <HeroLiveStatus slugs={outcomeSlugs} />

          {newsBlurb ? (
            <p className="mt-3 text-sm leading-relaxed text-white/45">{newsBlurb}</p>
          ) : null}

          <Link
            href={marketHref(firstSlug)}
            className="mt-5 inline-flex h-10 w-full items-center justify-center rounded-lg bg-[#05b169] text-sm font-bold text-black transition hover:brightness-110"
          >
            Trade this market
          </Link>
        </div>

        <div className="relative min-w-0 p-5">
          <div className="mt-1">
            <MultiLineChart market={{ ...market, outcomes }} height={300} />
          </div>
        </div>
      </div>
    </section>
  );
}

export function KalshiHeroFeature({ markets }: { markets: Market[] }) {
  return <KalshiHeroPanel markets={markets} />;
}

export function HeroFeatureRouter({ markets }: { markets: Market[] }) {
  const market = markets[0];
  if (market && isLiveMirror(market) && market.outcomes.length >= 2) {
    return <KalshiHeroFeature markets={markets} />;
  }
  return <HeroFeature markets={markets} />;
}
