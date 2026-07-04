import Link from "next/link";
import {
  cents,
  formatCompactUSD,
  type Market,
} from "@/lib/mock-data";

/*
 * QuestFlow-anatomy market card (matched to the real next.questflow.ai app):
 * icon tile + title, "Xd · $Vol." meta row, one row per outcome with the
 * price in teal cents and tinted Yes/No buttons, then a full-width outlined
 * "AI Analyze" action. Paper-trading: buttons deep-link to the market page.
 */

function daysLeft(endsAt: string): string {
  const ms = new Date(endsAt).getTime() - Date.now();
  if (!Number.isFinite(ms) || ms <= 0) return "closing";
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 24) return `${Math.max(hours, 1)}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function FeaturedMarketCard({ market }: { market: Market }) {
  const outcomes = market.outcomes.slice(0, 2);

  return (
    <div className="flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition duration-200 hover:border-border-light">
      <div className="flex items-start gap-4">
        <span className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-surface-3 text-2xl">
          {market.icon}
        </span>
        <div className="min-w-0 flex-1">
          <Link href={`/markets/${market.slug}`} className="block">
            <h3 className="line-clamp-2 text-lg font-bold leading-snug text-text hover:text-primary">
              {market.title}
            </h3>
          </Link>
          <div className="mt-2 flex items-center justify-between text-sm text-muted">
            <span>{daysLeft(market.endsAt)}</span>
            <span>{formatCompactUSD(market.volume)} Vol.</span>
          </div>
        </div>
      </div>

      <div className="mt-3 space-y-2.5">
        {outcomes.map((outcome) => (
          <div key={outcome.id} className="flex items-center gap-2.5">
            <span className="min-w-0 flex-1 truncate text-base font-medium text-text">
              {outcome.label}
            </span>
            <span className="shrink-0 text-base font-bold tabular-nums text-primary">
              {cents(outcome.price)}
            </span>
            <Link
              href={`/markets/${market.slug}?side=yes`}
              className="grid h-10 w-[72px] shrink-0 place-items-center rounded-xl bg-primary-dim text-sm font-semibold text-primary transition hover:bg-primary hover:text-bg"
            >
              Yes
            </Link>
            <Link
              href={`/markets/${market.slug}?side=no`}
              className="grid h-10 w-[72px] shrink-0 place-items-center rounded-xl bg-danger-dim text-sm font-semibold text-danger transition hover:bg-danger hover:text-white"
            >
              No
            </Link>
          </div>
        ))}
      </div>

      <Link
        href={`/markets/${market.slug}#ai`}
        className="mt-4 flex h-12 items-center justify-center gap-2 rounded-xl border border-primary/45 text-base font-medium text-primary transition hover:bg-primary-dim"
      >
        <SparkIcon />
        AI Analyze
      </Link>
    </div>
  );
}

function SparkIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" strokeLinejoin="round" />
      <path d="M19 3l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z" strokeLinejoin="round" />
    </svg>
  );
}
