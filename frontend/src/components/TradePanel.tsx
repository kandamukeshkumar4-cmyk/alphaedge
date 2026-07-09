"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { formatUSD, type Market } from "@/lib/mock-data";
import { placePaperOrder } from "@/lib/orders-api";
import { useAuth } from "@/hooks/useAuth";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import { useToast } from "./ToastProvider";
import { cn } from "@/lib/cn";

export function TradePanel({
  market,
  disabled = false,
}: {
  market: Market;
  disabled?: boolean;
}) {
  const { toast } = useToast();
  const { token, refreshBalance } = useAuth();
  const livePrice = useMarketPrice(market.slug);
  const [outcome, setOutcome] = useState<"yes" | "no">("yes");
  const [shares, setShares] = useState(10);
  const [submitting, setSubmitting] = useState(false);

  const staticYes = market.outcomes[0]?.price ?? 0.5;
  const price =
    outcome === "yes"
      ? livePrice.connected && livePrice.yes > 0
        ? livePrice.yes
        : staticYes
      : livePrice.connected && livePrice.no > 0
        ? livePrice.no
        : 1 - staticYes;

  const cost = useMemo(() => shares * price, [shares, price]);

  async function submit() {
    if (!token) return;
    if (shares < 1) {
      toast({ title: "Enter at least 1 share", tone: "error" });
      return;
    }

    setSubmitting(true);
    try {
      const result = await placePaperOrder(token, {
        slug: market.slug,
        side: "buy",
        outcome,
        shares,
        price,
      });
      await refreshBalance();
      toast({
        title: "Order placed",
        body: `Cost ${formatUSD(result.cost)} · Balance ${formatUSD(result.remaining_balance)}`,
        tone: "success",
      });
    } catch (error) {
      toast({
        title: "Order rejected",
        body: error instanceof Error ? error.message : "Unable to place order",
        tone: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-4 text-center">
        <p className="text-sm font-semibold text-text">Log in to trade</p>
        <Link
          href="/auth/login"
          className="mt-3 inline-flex rounded-xl bg-accent px-4 py-2 text-sm font-bold text-white transition hover:brightness-110"
        >
          Log In
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <div className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-bg p-1">
        <button
          type="button"
          onClick={() => setOutcome("yes")}
          className={cn(
            "rounded-lg py-2 text-sm font-bold transition",
            outcome === "yes" ? "bg-primary text-bg" : "text-muted hover:text-text",
          )}
        >
          Buy Yes
        </button>
        <button
          type="button"
          onClick={() => setOutcome("no")}
          className={cn(
            "rounded-lg py-2 text-sm font-bold transition",
            outcome === "no" ? "bg-danger text-bg" : "text-muted hover:text-text",
          )}
        >
          Buy No
        </button>
      </div>

      <div className="mt-3">
        <label
          htmlFor={`trade-shares-${market.slug}`}
          className="text-[11px] font-semibold uppercase tracking-wider text-muted-2"
        >
          Shares
        </label>
        <input
          id={`trade-shares-${market.slug}`}
          type="number"
          min={1}
          step={1}
          value={shares}
          onChange={(e) => setShares(Math.max(1, Math.floor(Number(e.target.value) || 1)))}
          className="mt-1.5 w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-text focus:border-accent focus:outline-none"
        />
      </div>

      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-muted">Price</dt>
          <dd className="font-mono font-bold text-text">{formatUSD(price)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-muted">Cost</dt>
          <dd className="font-mono font-bold text-primary">{formatUSD(cost)}</dd>
        </div>
      </dl>

      <button
        type="button"
        onClick={submit}
        disabled={disabled || submitting || shares < 1}
        className={cn(
          "mt-4 w-full rounded-xl py-2.5 text-sm font-bold transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50",
          outcome === "yes" ? "bg-primary text-bg" : "bg-danger text-bg",
        )}
      >
        {disabled
          ? "Market resolved"
          : submitting
            ? "Placing order…"
            : `Buy ${outcome.toUpperCase()}`}
      </button>

      <p className="mt-2 text-[11px] leading-relaxed text-muted-2">Paper simulation only.</p>
    </div>
  );
}
