"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import type { ReactNode } from "react";
import { useState } from "react";
import { MultiLineChart } from "./MultiLineChart";
import { RollingPrice } from "./RollingPrice";
import {
  pct,
  formatCompactUSD,
  timeUntil,
  type Market,
  type MarketOutcome,
  type OutcomeTone,
} from "@/lib/mock-data";
import { isLiveMirror } from "@/lib/hero-market";
import { useLiveMarket } from "@/hooks/useLiveMarket";
import { cn } from "@/lib/cn";

const TONE_BORDER: Record<OutcomeTone, string> = {
  primary: "border-primary/45 bg-primary-dim/55 text-primary",
  danger: "border-danger/45 bg-danger-dim/55 text-danger",
  accent: "border-sky-400/45 bg-sky-400/10 text-sky-300",
  gold: "border-gold/45 bg-gold/10 text-gold",
  muted: "border-border-light bg-surface-2 text-muted",
};

function outcomePriceSlug(outcome: MarketOutcome, market: Market): string {
  if (outcome.id.startsWith("pm-") || outcome.id.startsWith("ks-")) {
    return outcome.id;
  }
  return market.slug;
}

function LiveOutcomeCard({
  market,
  outcome,
  selected,
  onSelect,
}: {
  market: Market;
  outcome: MarketOutcome;
  selected: string;
  onSelect: (key: string) => void;
}) {
  const live = isLiveMirror(market);
  const slug = outcomePriceSlug(outcome, market);
  const tick = useLiveMarket(slug, live);

  const isComplement =
    live && !outcome.id.startsWith("pm-") && market.outcomes.length === 2 && outcome.id === "no";
  const hasLive = live && (tick.connected || tick.yes > 0);
  const yesPrice = hasLive ? (isComplement ? tick.no : tick.yes) : outcome.price;
  const noPrice = 1 - yesPrice;
  const flash = hasLive ? tick.flash : null;

  const yesKey = `${market.slug}:${outcome.id}:YES`;
  const noKey = `${market.slug}:${outcome.id}:NO`;
  const yesSelected = selected === yesKey;
  const noSelected = selected === noKey;

  return (
    <div className="rounded-md border border-border bg-bg/65 p-2.5 transition hover:border-border-light hover:bg-surface-2">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-border-light bg-surface text-xl">
          {outcome.emoji}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-base font-black text-text">{outcome.label}</div>
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-2">
            {live ? "Live Kalshi mirror" : "Paper order only"}
          </div>
        </div>
        <RollingPrice value={yesPrice} flash={flash} className="text-2xl" />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => onSelect(yesKey)}
          className={cn(
            "rounded-md border px-3 py-2 font-mono text-sm font-black transition",
            yesSelected
              ? "border-primary bg-primary text-bg"
              : "border-primary/55 bg-primary-dim text-primary hover:bg-primary hover:text-bg",
          )}
        >
          YES <RollingPrice value={yesPrice} flash={flash} className="text-sm" />
        </button>
        <button
          type="button"
          onClick={() => onSelect(noKey)}
          className={cn(
            "rounded-md border px-3 py-2 font-mono text-sm font-black transition",
            noSelected
              ? "border-danger bg-danger text-bg"
              : "border-danger/55 bg-danger-dim text-danger hover:bg-danger hover:text-bg",
          )}
        >
          NO {pct(noPrice)}
        </button>
      </div>
    </div>
  );
}

function LiveOutcomeLegend({
  market,
  outcome,
}: {
  market: Market;
  outcome: MarketOutcome;
}) {
  const live = isLiveMirror(market);
  const slug = outcomePriceSlug(outcome, market);
  const tick = useLiveMarket(slug, live);
  const isComplement =
    live && !outcome.id.startsWith("pm-") && market.outcomes.length === 2 && outcome.id === "no";
  const hasLive = live && (tick.connected || tick.yes > 0);
  const price = hasLive ? (isComplement ? tick.no : tick.yes) : outcome.price;

  return (
    <span className="flex items-center gap-1.5 text-sm">
      <span className={cn("h-2.5 w-2.5 rounded-full border", TONE_BORDER[outcome.tone])} />
      <span className="font-semibold text-muted">{outcome.label}</span>
      <RollingPrice value={price} flash={hasLive ? tick.flash : null} className="text-sm" />
    </span>
  );
}

export function HeroFeature({ markets }: { markets: Market[] }) {
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string>("");
  const market = markets[idx] ?? markets[0];
  if (!market) return null;

  const count = markets.length;
  const shown = market.outcomes.slice(0, 4);
  const live = isLiveMirror(market);
  const firstId = shown[0]?.id ?? "";
  const tradeSlug =
    firstId.startsWith("pm-") || firstId.startsWith("ks-") ? firstId : market.slug;

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card">
      <div className="grid lg:grid-cols-[410px_minmax(0,1fr)]">
        <div className="border-b border-border p-4 sm:p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <div className="text-[11px] font-black uppercase tracking-[0.14em] text-accent">
                  {live ? "Live featured" : "Featured market"}
                </div>
                {live && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary-dim px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-primary">
                    <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-primary" />
                    Kalshi live
                  </span>
                )}
              </div>
              <Link
                href={marketHref(tradeSlug)}
                className="mt-2 block text-3xl font-black leading-tight tracking-tight text-text transition hover:text-accent"
              >
                {market.title}
              </Link>
              <p className="mt-2 text-sm font-medium text-muted">{market.question}</p>
            </div>
            <div className="flex items-center gap-1.5">
              <IconButton label="Save market">
                <StarIcon />
              </IconButton>
              <IconButton label="Share market">
                <ShareIcon />
              </IconButton>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {shown.map((outcome) => (
              <LiveOutcomeCard
                key={outcome.id}
                market={market}
                outcome={outcome}
                selected={selected}
                onSelect={setSelected}
              />
            ))}
          </div>

          <Link
            href={marketHref(tradeSlug)}
            className="mt-4 inline-flex h-11 w-full items-center justify-center rounded-xl bg-accent px-4 text-sm font-black text-white shadow-glow transition hover:brightness-110"
          >
            Trade this market
          </Link>

          <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-xs text-muted">
            <Stat label="Volume" value={formatCompactUSD(market.volume)} />
            <Stat
              label={live ? "Markets" : "Traders"}
              value={live ? String(market.marketCount ?? 1) : market.traders.toLocaleString()}
            />
            <Stat label="Closes" value={timeUntil(market.endsAt)} />
          </div>
        </div>

        <div className="min-w-0 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-black uppercase tracking-[0.14em] text-gold">
                {market.category}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-3">
                {shown.map((outcome) => (
                  <LiveOutcomeLegend key={outcome.id} market={market} outcome={outcome} />
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden rounded-full border border-accent/40 bg-accent-dim px-2.5 py-1 text-xs font-black uppercase tracking-[0.1em] text-accent sm:inline-flex">
                Simulated funds only
              </span>
              {count > 1 && (
                <>
                  <button
                    type="button"
                    onClick={() => setIdx((p) => (p - 1 + count) % count)}
                    className="grid h-9 w-9 place-items-center rounded-md border border-border text-muted transition hover:border-border-light hover:text-text"
                    aria-label="Previous featured market"
                  >
                    <ChevronLeftIcon />
                  </button>
                  <button
                    type="button"
                    onClick={() => setIdx((p) => (p + 1) % count)}
                    className="grid h-9 w-9 place-items-center rounded-md border border-border text-muted transition hover:border-border-light hover:text-text"
                    aria-label="Next featured market"
                  >
                    <ChevronRightIcon />
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="mt-6 rounded-md border border-border bg-bg/55 p-3 sm:p-4">
            <MultiLineChart market={market} height={270} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-sm font-black text-text tabular">{value}</div>
      <div className="mt-0.5 text-[10px] font-black uppercase tracking-[0.12em] text-muted-2">
        {label}
      </div>
    </div>
  );
}

function IconButton({ label, children }: { label: string; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="grid h-8 w-8 place-items-center rounded-md border border-border text-muted transition hover:border-border-light hover:text-text"
    >
      {children}
    </button>
  );
}

function StarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path
        d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ShareIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 16V4" strokeLinecap="round" />
      <path d="m7 9 5-5 5 5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 14v5h14v-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m15 18-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m9 18 6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
