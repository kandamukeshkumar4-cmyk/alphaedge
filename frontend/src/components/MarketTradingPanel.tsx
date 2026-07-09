"use client";

/**
 * Market analysis panel — prices + ATLAS entry.
 * Order placement UI removed from product UX (analysis assistant reposition).
 * Backend paper APIs remain; this surface does not submit orders.
 */

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchLatestPrice } from "@/lib/alphaedge-api";
import { useAtlasPanel } from "@/context/atlas-panel";
import { useInterval } from "@/hooks/useInterval";
import { PAPER_ONLY_NOTE } from "@/lib/product-disclaimer";

type MarketStatus = "open" | "closed" | "resolved";

type Props = {
  slug: string;
  title: string;
  status?: MarketStatus;
  closeTime?: string;
  initialYesPrice?: number;
};

export function MarketTradingPanel({
  slug,
  title,
  status = "open",
  closeTime,
  initialYesPrice = 0.5,
}: Props) {
  const { openPanel } = useAtlasPanel();
  const [yesPrice, setYesPrice] = useState(initialYesPrice);

  const noPrice = Math.round((1 - yesPrice) * 10000) / 10000;

  const refreshPrice = useCallback(async () => {
    const live = await fetchLatestPrice(slug);
    if (live && live.yes > 0) {
      setYesPrice(live.yes);
    }
  }, [slug]);

  useEffect(() => {
    void refreshPrice();
  }, [refreshPrice]);

  useInterval(refreshPrice, 30_000);

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="line-clamp-1 text-sm font-bold text-text">{title}</p>
        <span
          className={cn(
            "shrink-0 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
            status === "open"
              ? "bg-primary/20 text-primary"
              : "bg-muted-2/20 text-muted-2",
          )}
        >
          {status}
        </span>
      </div>

      {closeTime ? (
        <p className="mb-3 text-[11px] text-muted-2">
          Closes{" "}
          {new Date(closeTime).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
      ) : null}

      <div className="mb-3 overflow-hidden rounded-lg border border-border">
        <div className="relative flex h-7 text-[11px] font-bold">
          <div
            className="flex items-center justify-center bg-primary/20 text-primary transition-all"
            style={{ width: `${yesPrice * 100}%` }}
          >
            YES {(yesPrice * 100).toFixed(0)}¢
          </div>
          <div className="flex flex-1 items-center justify-center bg-danger/20 text-danger">
            NO {(noPrice * 100).toFixed(0)}¢
          </div>
        </div>
      </div>

      <p className="mb-3 text-xs leading-relaxed text-muted">
        Live book snapshot for research. AlphaEdge does not place bets in-app —
        use AI Analyze or ATLAS for briefs and signals.
      </p>

      <button
        type="button"
        onClick={() =>
          openPanel({
            mode: "analyze",
            marketSlug: slug,
            marketTitle: title,
            seedPrompt: `Analyze ${title}. Current YES ~${Math.round(yesPrice * 100)}¢.`,
          })
        }
        className="w-full rounded-xl border border-primary/40 bg-primary-dim py-2.5 text-sm font-bold text-primary shadow-glow transition hover:bg-primary hover:text-bg"
      >
        ✦ AI Analyze
      </button>

      <p className="mt-2 text-[10px] leading-relaxed text-muted-2">{PAPER_ONLY_NOTE}</p>
    </div>
  );
}
