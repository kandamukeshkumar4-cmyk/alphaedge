import Link from "next/link";
import {
  pct,
  formatCompactUSD,
  generateCandles,
  type Market,
  type OutcomeTone,
} from "@/lib/mock-data";
import { cn } from "@/lib/cn";
import { marketCountLabel } from "@/lib/market-copy";
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

export function FeaturedMarketCard({ market }: { market: Market }) {
  const primary = market.outcomes[0];
  const secondary = market.outcomes[1];
  const compared = secondary ? [primary, secondary] : [primary];
  const spark = generateCandles(market.slug, 36, primary.price, 900).map((c) => c.close);
  const up = spark[spark.length - 1] >= spark[0];

  return (
    <Link
      href={`/markets/${market.slug}`}
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
          {pct(primary.price)}
        </div>
      </div>

      <div className="mt-4 grid flex-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_144px]">
        <div className="min-w-0">
          <Sparkline data={spark} up={up} width={260} height={54} className="h-[54px] w-full" />
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {compared.map((outcome) => (
              <span key={outcome.id} className="flex items-center gap-1.5 text-muted">
                <span className={cn("h-2 w-2 rounded-full", DOT[outcome.tone])} />
                <span className="truncate">{outcome.label}</span>
                <span className="font-mono font-black text-text tabular">
                  {pct(outcome.price)}
                </span>
              </span>
            ))}
          </div>
        </div>

        <div className="grid gap-2">
          <span className="rounded-xl border border-primary/55 bg-primary-dim px-3 py-2 text-center font-mono text-xs font-black text-primary transition group-hover:bg-primary group-hover:text-bg">
            YES {pct(primary.price)}
          </span>
          <span className="rounded-xl border border-danger/55 bg-danger-dim px-3 py-2 text-center font-mono text-xs font-black text-danger">
            NO {pct(1 - primary.price)}
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
