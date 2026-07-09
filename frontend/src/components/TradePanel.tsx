"use client";

/**
 * Legacy trade panel — analysis-only after product reposition.
 * Does not submit orders; points users to ATLAS / market analysis.
 */

import { type Market } from "@/lib/mock-data";
import { useAtlasPanel } from "@/context/atlas-panel";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import { PAPER_ONLY_NOTE } from "@/lib/product-disclaimer";
import { cn } from "@/lib/cn";

export function TradePanel({
  market,
  disabled = false,
}: {
  market: Market;
  disabled?: boolean;
}) {
  const { openPanel } = useAtlasPanel();
  const livePrice = useMarketPrice(market.slug);
  const staticYes = market.outcomes[0]?.price ?? 0.5;
  const yes =
    livePrice.connected && livePrice.yes > 0 ? livePrice.yes : staticYes;
  const no =
    livePrice.connected && livePrice.no > 0 ? livePrice.no : 1 - staticYes;

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <p className="mb-2 text-sm font-bold text-text">Market snapshot</p>
      <div className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-bg p-1">
        <div
          className={cn(
            "rounded-lg py-2 text-center text-sm font-bold",
            "bg-primary/15 text-primary",
          )}
        >
          YES {(yes * 100).toFixed(0)}¢
        </div>
        <div className="rounded-lg py-2 text-center text-sm font-bold bg-danger/15 text-danger">
          NO {(no * 100).toFixed(0)}¢
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">
        {disabled
          ? "Market closed — research history only."
          : "Analysis assistant — no bets placed in-app."}
      </p>
      <button
        type="button"
        disabled={disabled}
        onClick={() =>
          openPanel({
            mode: "analyze",
            marketSlug: market.slug,
            marketTitle: market.title,
            seedPrompt: `Analyze ${market.title}. Current YES ~${Math.round(yes * 100)}¢.`,
          })
        }
        className="mt-3 w-full rounded-xl border border-primary/40 bg-primary-dim py-2.5 text-sm font-bold text-primary transition hover:bg-primary hover:text-bg disabled:cursor-not-allowed disabled:opacity-50"
      >
        ✦ AI Analyze
      </button>
      <p className="mt-2 text-[10px] leading-relaxed text-muted-2">{PAPER_ONLY_NOTE}</p>
    </div>
  );
}
