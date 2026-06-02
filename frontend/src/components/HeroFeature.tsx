"use client";

import Link from "next/link";
import { useState } from "react";
import { MultiLineChart } from "./MultiLineChart";
import {
  pct,
  multiplier,
  formatCompactUSD,
  timeUntil,
  type Market,
  type OutcomeTone,
} from "@/lib/mock-data";
import { cn } from "@/lib/cn";

const PILL: Record<OutcomeTone, string> = {
  primary: "border-primary/40 text-primary",
  danger: "border-danger/40 text-danger",
  accent: "border-accent/40 text-accent",
  gold: "border-gold/40 text-gold",
  muted: "border-border-light text-muted",
};

export function HeroFeature({ markets }: { markets: Market[] }) {
  const [idx, setIdx] = useState(0);
  const market = markets[idx];
  const count = markets.length;
  const shown = market.outcomes.slice(0, 4);

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-surface-2 text-lg">
            {market.icon}
          </span>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-muted-2">
              {market.category}
            </div>
            <Link
              href={`/markets/${market.slug}`}
              className="text-base font-black leading-tight text-text transition hover:text-accent sm:text-lg"
            >
              {market.title}
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted">
          <span className="font-mono text-xs">
            {idx + 1} of {count}
          </span>
          <button
            onClick={() => setIdx((p) => (p - 1 + count) % count)}
            className="grid h-7 w-7 place-items-center rounded-md border border-border transition hover:border-border-light hover:text-text"
            aria-label="Previous"
          >
            ‹
          </button>
          <button
            onClick={() => setIdx((p) => (p + 1) % count)}
            className="grid h-7 w-7 place-items-center rounded-md border border-border transition hover:border-border-light hover:text-text"
            aria-label="Next"
          >
            ›
          </button>
        </div>
      </div>

      {/* Body: outcomes table (left) + chart (right) — Kalshi featured layout */}
      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <div className="min-w-0">
          {/* Column headers */}
          <div className="grid grid-cols-[minmax(0,1fr)_auto_56px] items-center gap-3 border-b border-border px-1 pb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-2">
            <span>Market</span>
            <span className="text-right">Payout</span>
            <span className="text-right">Chance</span>
          </div>

          {/* Outcome rows */}
          <div className="divide-y divide-border">
            {shown.map((o) => (
              <Link
                key={o.id}
                href={`/markets/${market.slug}`}
                className="grid grid-cols-[minmax(0,1fr)_auto_56px] items-center gap-3 px-1 py-2.5 transition hover:bg-surface-2"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface-2 text-sm">
                    {o.emoji}
                  </span>
                  <span className="truncate text-sm font-semibold text-text">
                    {o.label}
                  </span>
                </span>
                <span className="text-right font-mono text-xs text-muted-2">
                  {multiplier(o.price)}
                </span>
                <span
                  className={cn(
                    "rounded-md border py-1 text-center font-mono text-sm font-black",
                    PILL[o.tone],
                  )}
                >
                  {pct(o.price)}
                </span>
              </Link>
            ))}
          </div>

          {/* AI line */}
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-primary/25 bg-primary-dim px-3 py-2">
            <span className="text-sm">🤖</span>
            <span className="text-xs font-semibold text-text">
              AI model {pct(market.forecast.prob)}
            </span>
            <span className="ml-auto font-mono text-[11px] font-bold text-primary">
              edge {market.forecast.edge >= 0 ? "+" : ""}
              {Math.round(market.forecast.edge * 100)}%
            </span>
          </div>

          {/* Footer stats + CTA */}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span className="font-mono">{formatCompactUSD(market.volume)} Vol.</span>
            <span className="font-mono">{market.traders.toLocaleString()} traders</span>
            <span className="font-mono">{timeUntil(market.endsAt)} left</span>
          </div>
          <Link
            href={`/markets/${market.slug}`}
            className="mt-3 inline-block w-full rounded-lg bg-primary px-4 py-2.5 text-center text-sm font-bold text-white transition hover:bg-accent"
          >
            Trade this market
          </Link>
        </div>

        {/* Multi-line outcome chart (live + hover-reactive) + context */}
        <div className="min-w-0">
          <div className="rounded-xl border border-border bg-bg/40 p-3">
            <MultiLineChart market={market} height={260} />
          </div>
          <p className="mt-2 line-clamp-2 px-1 text-xs leading-relaxed text-muted-2">
            <span className="font-semibold text-muted">Context</span> · {market.forecast.reasoning}
          </p>
        </div>
      </div>
    </div>
  );
}
