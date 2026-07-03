"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { formatCompactUSD, type Market, type MarketOutcome, type OutcomeTone } from "@/lib/mock-data";
import { useLivePrice } from "@/context/live-prices";
import { useLiveSparkline } from "@/hooks/useLiveSparkline";
import { isKalshiMatchCard } from "@/lib/hero-market";
import { resolveOutcomeSlug } from "@/lib/live-price";
import { flagForTeam } from "@/lib/team-flags";
import { cn } from "@/lib/cn";
import { marketCountLabel } from "@/lib/market-copy";
import { RollingPrice } from "./RollingPrice";
import { Sparkline } from "./Sparkline";

const CATEGORY_COLOR: Record<Market["category"], string> = {
  Sports: "text-gold",
  Politics: "text-sky-400",
  Crypto: "text-orange-400",
  Culture: "text-fuchsia-400",
  Economics: "text-teal-300",
};

const DOT: Record<OutcomeTone, string> = {
  primary: "bg-primary",
  danger: "bg-danger",
  accent: "bg-sky-400",
  gold: "bg-gold",
  muted: "bg-muted",
};

function OutcomeLivePill({
  outcome,
  market,
  compact = false,
}: {
  outcome: MarketOutcome;
  market: Market;
  compact?: boolean;
}) {
  const slug = resolveOutcomeSlug(outcome.id, market.slug);
  const live = useLivePrice(slug, outcome.price);
  const price = live.price > 0 || live.connected ? live.price : outcome.price;
  const isTie = /tie|draw/i.test(outcome.label);

  return (
    <span
      className={cn(
        "flex items-center justify-center gap-1.5 rounded-xl border px-2 py-2 text-center font-mono text-xs font-black tabular",
        isTie
          ? "border-border-light bg-surface-2 text-muted"
          : outcome.tone === "primary"
            ? "border-primary/55 bg-primary-dim text-primary"
            : "border-accent/50 bg-accent/10 text-accent",
        compact && "px-1.5 py-1.5 text-[10px]",
      )}
    >
      <span className="text-sm leading-none">{flagForTeam(outcome.label)}</span>
      <span className="truncate">{outcome.label}</span>
      <RollingPrice value={price} flash={live.flash} className="text-inherit" />
    </span>
  );
}

function KalshiMatchFeaturedCard({ market }: { market: Market }) {
  const outcomes = market.outcomes.slice(0, 4);
  const favorite = outcomes.reduce(
    (best, o) => (o.price > best.price ? o : best),
    outcomes[0],
  );
  const favSlug = resolveOutcomeSlug(favorite.id, market.slug);
  const favLive = useLivePrice(favSlug, favorite.price);
  const favPrice = favLive.price > 0 || favLive.connected ? favLive.price : favorite.price;
  const { data: spark, up } = useLiveSparkline(favSlug, favorite.price, market.source);
  const linkSlug = resolveOutcomeSlug(outcomes[0]?.id ?? "", market.slug) || market.slug;

  return (
    <Link
      href={marketHref(linkSlug)}
      className="group flex min-h-[200px] flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-accent hover:bg-surface-2 hover:shadow-glow"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-black uppercase tracking-[0.14em] text-gold">
            ⚽ Live match
          </div>
          <h3 className="mt-2 line-clamp-2 text-lg font-black leading-snug text-text">
            {market.title}
          </h3>
          <p className="mt-1 line-clamp-1 text-xs font-medium text-muted">
            Kalshi mirror · {market.marketCount} outcomes
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-2">
            {favorite.label}
          </div>
          <div className="font-mono text-4xl font-black leading-none text-text tabular">
            <RollingPrice value={favPrice} flash={favLive.flash} className="text-4xl" />
          </div>
        </div>
      </div>

      <div className="mt-4 flex-1">
        <Sparkline
          data={spark}
          up={up}
          width={260}
          height={54}
          className="h-[54px] w-full"
        />
        <div className="mt-3 grid grid-cols-3 gap-2">
          {outcomes.map((outcome) => (
            <OutcomeLivePill key={outcome.id} outcome={outcome} market={market} compact />
          ))}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 font-mono text-[11px] text-muted">
        <span>{formatCompactUSD(market.volume)} Vol.</span>
        <span className="text-muted">Kalshi mirror</span>
        <span>{marketCountLabel(market.marketCount)}</span>
      </div>
    </Link>
  );
}

function BinaryFeaturedCard({ market }: { market: Market }) {
  const primary = market.outcomes[0];
  const secondary = market.outcomes[1];
  const compared = secondary ? [primary, secondary] : [primary];
  const live = useLivePrice(market.slug, primary.price);
  const yesPrice = live.price > 0 || live.connected ? live.price : primary.price;
  const noPrice = 1 - yesPrice;
  const { data: spark, up } = useLiveSparkline(market.slug, primary.price, market.source);

  return (
    <Link
      href={marketHref(market.slug)}
      className="group flex min-h-[180px] flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-accent hover:bg-surface-2 hover:shadow-glow"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div
            className={cn(
              "text-[11px] font-black uppercase tracking-[0.14em]",
              CATEGORY_COLOR[market.category],
            )}
          >
            {market.category}
          </div>
          <h3 className="mt-2 line-clamp-2 text-lg font-black leading-snug text-text">
            {market.title}
          </h3>
          <p className="mt-1 line-clamp-1 text-xs font-medium text-muted">
            {market.question}
          </p>
        </div>
        <div className="shrink-0 text-right font-mono text-4xl font-black leading-none text-text tabular">
          <RollingPrice value={yesPrice} flash={live.flash} className="text-4xl" />
        </div>
      </div>

      <div className="mt-4 grid flex-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_144px]">
        <div className="min-w-0">
          <Sparkline
            data={spark}
            up={up}
            width={260}
            height={54}
            className="h-[54px] w-full"
          />
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {compared.map((outcome) => {
              const price = outcome.id === primary.id ? yesPrice : noPrice;
              return (
                <span key={outcome.id} className="flex items-center gap-1.5 text-muted">
                  <span className={cn("h-2 w-2 rounded-full", DOT[outcome.tone])} />
                  <span className="truncate">{outcome.label}</span>
                  <RollingPrice
                    value={price}
                    flash={outcome.id === primary.id ? live.flash : null}
                    className="text-xs"
                  />
                </span>
              );
            })}
          </div>
        </div>

        <div className="grid gap-2">
          <span className="rounded-xl border border-primary/55 bg-primary-dim px-3 py-2 text-center font-mono text-xs font-black text-primary transition group-hover:bg-primary group-hover:text-bg">
            YES{" "}
            <RollingPrice value={yesPrice} flash={live.flash} className="text-xs text-inherit" />
          </span>
          <span className="rounded-xl border border-danger/55 bg-danger-dim px-3 py-2 text-center font-mono text-xs font-black text-danger">
            NO{" "}
            <RollingPrice
              value={noPrice}
              flash={live.flash === "up" ? "down" : live.flash === "down" ? "up" : null}
              className="text-xs text-inherit"
            />
          </span>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 font-mono text-[11px] text-muted">
        <span>{formatCompactUSD(market.volume)} Vol.</span>
        <span>{market.traders.toLocaleString()} traders</span>
        <span>{marketCountLabel(market.marketCount)}</span>
      </div>
    </Link>
  );
}

export function FeaturedMarketCard({ market }: { market: Market }) {
  if (isKalshiMatchCard(market)) {
    return <KalshiMatchFeaturedCard market={market} />;
  }
  return <BinaryFeaturedCard market={market} />;
}
