"use client";

import { CANONICAL_SLUG } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { useLivePrices } from "@/lib/use-live-prices";

/*
 * Loop V90 (C3) — visible wiring for the useLivePrices polling hook.
 *
 * Charter note (STATE90C.md): C3 asks to wire the hook into a visible price
 * surface, while the charter bounds this node to notifications/** (plus the
 * SiteHeader bell and this file's neighbors). This chip lives inside the
 * notification dropdown — always visible when the bell opens — so live
 * updates are demonstrable without touching any out-of-charter component.
 * Paper price, research display only.
 */

function formatCents(price: number | null): string {
  if (price === null) return "—";
  return `${(price * 100).toFixed(1)}¢`;
}

function formatClock(iso: string | null): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleTimeString("en-US", { hour12: false });
}

export function LivePriceChip() {
  const { price, loading, lastUpdated, source } = useLivePrices(CANONICAL_SLUG);

  return (
    <div
      data-testid="live-price-chip"
      className="flex items-center gap-2 font-mono text-[11px] text-muted"
      title="Polls every 15s (pauses when the tab is hidden) — paper price, research only"
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-1.5 w-1.5 shrink-0 rounded-full",
          loading ? "bg-muted-2" : "animate-pulse-soft bg-primary motion-reduce:animate-none",
        )}
      />
      <span className="font-bold uppercase tracking-[0.08em] text-text">LAL·BOS YES</span>
      <span className="font-bold text-primary">{formatCents(price)}</span>
      <span
        className={cn(
          "rounded border px-1 py-px text-[9px] font-bold uppercase tracking-[0.1em]",
          source === "live"
            ? "border-primary/40 bg-primary-dim/60 text-primary"
            : "border-border-light bg-surface-2 text-muted-2",
        )}
      >
        {source === "live" ? "live" : "mock"}
      </span>
      <span className="ml-auto shrink-0 text-muted-2">
        {loading ? "fetching…" : `upd ${formatClock(lastUpdated)}`}
      </span>
    </div>
  );
}
