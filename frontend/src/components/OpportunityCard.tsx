"use client";

// Shared opportunity row/card — the ranked model-vs-market edge card. Used by
// the R01 scanner (/opportunities) and the S02 category dashboard
// (/categories/[category]) so both surfaces render identical rows. Analysis
// only: NOT an order feed; the row deep-links to the market's paper-trade panel.
import Link from "next/link";
import type { OpportunityRowView } from "@/lib/opportunities-api";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { cn } from "@/lib/cn";

const ptsFmt = (n: number) => `${(n * 100).toFixed(1)} pts`;

export function OpportunityCard({ row }: { row: OpportunityRowView }) {
  return (
    <article className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={row.href}
            className="block truncate text-sm font-bold text-text hover:text-primary hover:underline"
          >
            {row.title}
          </Link>
          <p className="mt-0.5 truncate font-mono text-[11px] text-muted-2">{row.slug}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-1 font-mono text-[11px] font-black",
            row.directionTone === "up"
              ? "border-up/40 bg-up/10 text-up"
              : "border-danger/40 bg-danger/10 text-danger",
          )}
        >
          {row.direction} lean
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-lg border border-accent/40 bg-accent/12 px-2.5 py-1.5 font-mono text-sm font-black text-accent">
          edge <AnimatedNumber value={row.edge} format={ptsFmt} />
        </span>
        <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-xs font-bold text-text">
          model {row.modelLabel}
        </span>
        <span className="rounded-lg bg-surface-2 px-2.5 py-1.5 font-mono text-xs font-bold text-muted">
          market {row.marketLabel}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-muted-2">
        <span>
          YES price {row.yesPriceLabel ?? <span className="text-muted-2">n/a</span>}
        </span>
        <span>liquidity {row.liquidityLabel}</span>
        {row.family ? <span className="text-accent">{row.family}</span> : null}
      </div>

      {row.evidence ? <SignalEvidenceBlock evidence={row.evidence} /> : null}

      <div className="mt-3 border-t border-border pt-3">
        <Link
          href={row.href}
          className="text-[11px] font-semibold text-accent hover:underline"
        >
          Open market &amp; paper-trade panel →
        </Link>
      </div>
    </article>
  );
}
