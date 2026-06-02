import Link from "next/link";
import {
  multiplier,
  pct,
  formatCompactUSD,
  type Market,
  type OutcomeTone,
} from "@/lib/mock-data";
import { cn } from "@/lib/cn";
import { marketCountLabel } from "@/lib/market-copy";

const BAR: Record<OutcomeTone, string> = {
  primary: "bg-primary",
  danger: "bg-danger",
  accent: "bg-accent",
  gold: "bg-gold",
  muted: "bg-muted",
};

const PILL: Record<OutcomeTone, string> = {
  primary: "border-primary/40 text-primary",
  danger: "border-danger/40 text-danger",
  accent: "border-accent/40 text-accent",
  gold: "border-gold/40 text-gold",
  muted: "border-border-light text-muted",
};

export function MarketCard({ market }: { market: Market }) {
  const shown = market.outcomes.slice(0, 3);
  const edgeUp = market.forecast.edge >= 0;

  return (
    <Link
      href={`/markets/${market.slug}`}
      className="group flex flex-col rounded-xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-border-light hover:shadow-lift"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="grid h-6 w-6 place-items-center rounded bg-surface-2 text-sm">
            {market.icon}
          </span>
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-2">
            {market.category}
          </span>
        </div>
        <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-primary">
          🤖 {edgeUp ? "+" : ""}
          {Math.round(market.forecast.edge * 100)}%
        </span>
      </div>

      {/* Title */}
      <h3 className="mt-2.5 line-clamp-2 min-h-[2.5rem] text-sm font-bold leading-snug text-text">
        {market.title}
      </h3>

      {/* Outcome rows — Kalshi style */}
      <div className="mt-2 space-y-2.5">
        {shown.map((o) => (
          <div key={o.id} className="grid grid-cols-[minmax(0,1fr)_auto_46px] items-center gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs">{o.emoji}</span>
                <span className="truncate text-sm text-text">{o.label}</span>
              </div>
              <div className="mt-1 h-[3px] w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className={cn("h-full rounded-full", BAR[o.tone])}
                  style={{ width: `${Math.round(o.price * 100)}%` }}
                />
              </div>
            </div>
            <span className="font-mono text-[11px] text-muted-2">{multiplier(o.price)}</span>
            <span
              className={cn(
                "rounded-full border py-0.5 text-center font-mono text-xs font-bold",
                PILL[o.tone],
              )}
            >
              {pct(o.price)}
            </span>
          </div>
        ))}
        {market.outcomes.length > 3 && (
          <div className="text-[11px] text-muted-2">
            +{market.outcomes.length - 3} more
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5 font-mono text-[11px] text-muted">
        <span>{formatCompactUSD(market.volume)} Vol.</span>
        <span>{marketCountLabel(market.marketCount)}</span>
      </div>
    </Link>
  );
}
