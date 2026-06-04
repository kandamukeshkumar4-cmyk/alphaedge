"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useState } from "react";
import { MultiLineChart } from "./MultiLineChart";
import {
  pct,
  formatCompactUSD,
  timeUntil,
  type Market,
  type OutcomeTone,
} from "@/lib/mock-data";
import { cn } from "@/lib/cn";

const TONE_BORDER: Record<OutcomeTone, string> = {
  primary: "border-primary/45 bg-primary-dim/55 text-primary",
  danger: "border-danger/45 bg-danger-dim/55 text-danger",
  accent: "border-sky-400/45 bg-sky-400/10 text-sky-300",
  gold: "border-gold/45 bg-gold/10 text-gold",
  muted: "border-border-light bg-surface-2 text-muted",
};

export function HeroFeature({ markets }: { markets: Market[] }) {
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string>("");
  const market = markets[idx] ?? markets[0];
  if (!market) return null;

  const count = markets.length;
  const shown = market.outcomes.slice(0, 4);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
      <div className="grid lg:grid-cols-[410px_minmax(0,1fr)]">
        <div className="border-b border-border p-4 sm:p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-black uppercase tracking-[0.14em] text-primary">
                Featured market
              </div>
              <Link
                href={`/markets/${market.slug}`}
                className="mt-2 block text-3xl font-black leading-tight tracking-tight text-text transition hover:text-primary"
              >
                {market.title}
              </Link>
              <p className="mt-2 text-sm font-medium text-muted">
                {market.question}
              </p>
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
            {shown.map((outcome) => {
              const yesKey = `${market.slug}:${outcome.id}:YES`;
              const noKey = `${market.slug}:${outcome.id}:NO`;
              const yesSelected = selected === yesKey;
              const noSelected = selected === noKey;
              return (
                <div
                  key={outcome.id}
                  className="rounded-md border border-border bg-bg/65 p-2.5 transition hover:border-border-light hover:bg-surface-2"
                >
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-border-light bg-surface text-xl">
                      {outcome.emoji}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-base font-black text-text">
                        {outcome.label}
                      </div>
                      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-2">
                        Paper order only
                      </div>
                    </div>
                    <div className="font-mono text-2xl font-black tabular text-text">
                      {pct(outcome.price)}
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setSelected(yesKey)}
                      className={cn(
                        "rounded-md border px-3 py-2 font-mono text-sm font-black transition",
                        yesSelected
                          ? "border-primary bg-primary text-bg"
                          : "border-primary/55 bg-primary-dim text-primary hover:bg-primary hover:text-bg",
                      )}
                    >
                      YES {pct(outcome.price)}
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelected(noKey)}
                      className={cn(
                        "rounded-md border px-3 py-2 font-mono text-sm font-black transition",
                        noSelected
                          ? "border-danger bg-danger text-bg"
                          : "border-danger/55 bg-danger-dim text-danger hover:bg-danger hover:text-bg",
                      )}
                    >
                      NO {pct(1 - outcome.price)}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <Link
            href={`/markets/${market.slug}`}
            className="mt-4 inline-flex h-11 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-black text-bg shadow-glow transition hover:bg-accent"
          >
            Trade this market
          </Link>

          <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-xs text-muted">
            <Stat label="Volume" value={formatCompactUSD(market.volume)} />
            <Stat label="Traders" value={market.traders.toLocaleString()} />
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
                  <span key={outcome.id} className="flex items-center gap-1.5 text-sm">
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full border",
                        TONE_BORDER[outcome.tone],
                      )}
                    />
                    <span className="font-semibold text-muted">{outcome.label}</span>
                    <span className="font-mono font-black text-text tabular">
                      {pct(outcome.price)}
                    </span>
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden rounded-md border border-primary/40 bg-primary-dim px-2.5 py-1 text-xs font-black uppercase tracking-[0.1em] text-primary sm:inline-flex">
                Simulated funds only
              </span>
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
