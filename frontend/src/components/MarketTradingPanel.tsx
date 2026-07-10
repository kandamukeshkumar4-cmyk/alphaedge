"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { API_BASE, fetchLatestPrice } from "@/lib/alphaedge-api";
import { placePaperOrder } from "@/lib/orders-api";
import { fetchPortfolio } from "@/lib/portfolio-api";
import { useAuth } from "@/hooks/useAuth";
import { useInterval } from "@/hooks/useInterval";
import { useToast } from "./ToastProvider";
import { PositionCard, type Position } from "./PositionCard";
import { useGamification } from "@/lib/gamification";

function formatUSD(v: number) {
  return `$${v.toFixed(2)}`;
}

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
  const { toast } = useToast();
  const { token, paperBalance, refreshBalance } = useAuth();
  const { markTradePlaced } = useGamification();

  const [yesPrice, setYesPrice] = useState(initialYesPrice);
  const [outcome, setOutcome] = useState<"yes" | "no">("yes");
  const [amount, setAmount] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  // One Idempotency-Key per trade intent — see TradePanel for the pattern.
  const idemKeyRef = useRef<string | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [positionLoading, setPositionLoading] = useState(false);

  const noPrice = Math.round((1 - yesPrice) * 10000) / 10000;
  const price = outcome === "yes" ? yesPrice : noPrice;
  const cost = useMemo(() => amount * price, [amount, price]);
  const maxShares = useMemo(
    () => (paperBalance != null && price > 0 ? Math.floor(paperBalance / price) : 0),
    [paperBalance, price],
  );

  const refreshPrice = useCallback(async () => {
    const live = await fetchLatestPrice(slug);
    if (live && live.yes > 0) {
      setYesPrice(live.yes);
    }
  }, [slug]);

  const refreshPosition = useCallback(async () => {
    if (!token) return;
    setPositionLoading(true);
    try {
      const portfolio = await fetchPortfolio(token, { apiBase: API_BASE || "http://localhost:8000" });
      const match = portfolio.positions.find(
        (p) => p.market_slug === slug && !p.settled,
      );
      if (match) {
        setPosition({
          market_slug: match.market_slug,
          outcome: match.outcome,
          shares: match.quantity,
          avg_cost: match.price ?? 0,
          current_price: match.current_price ?? null,
          unrealized_pnl: match.unrealized_pnl ?? null,
          pnl_pct: match.pnl_pct ?? null,
        });
      } else {
        setPosition(null);
      }
    } catch {
      // position display is optional
    } finally {
      setPositionLoading(false);
    }
  }, [token, slug]);

  useEffect(() => {
    void refreshPrice();
    void refreshPosition();
  }, [refreshPrice, refreshPosition]);

  useInterval(refreshPrice, 30_000);

  async function submit() {
    if (!token) return;
    if (amount < 1) {
      toast({ title: "Enter at least 1 share", tone: "error" });
      return;
    }
    setSubmitting(true);
    idemKeyRef.current ??= crypto.randomUUID();
    try {
      const result = await placePaperOrder(
        token,
        { slug, side: "buy", outcome, shares: amount, price },
        idemKeyRef.current,
      );
      idemKeyRef.current = null;
      await Promise.all([refreshBalance(), refreshPosition()]);
      markTradePlaced();
      toast({
        title: "Order placed",
        body: `Cost ${formatUSD(result.cost)} · Balance ${formatUSD(result.remaining_balance)}`,
        tone: "success",
      });
    } catch (err) {
      if (!(err instanceof TypeError)) idemKeyRef.current = null;
      toast({
        title: "Order rejected",
        body: err instanceof Error ? err.message : "Unable to place order",
        tone: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  const isDisabled = status !== "open";

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
      {/* Header */}
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

      {closeTime && (
        <p className="mb-3 text-[11px] text-muted-2">
          Closes {new Date(closeTime).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
        </p>
      )}

      {/* YES/NO price bar */}
      <div className="mb-3 overflow-hidden rounded-lg border border-border">
        <div className="relative flex h-7 text-[11px] font-bold">
          <div
            className="flex items-center justify-center bg-primary/20 text-primary transition-all"
            style={{ width: `${yesPrice * 100}%` }}
          >
            YES {(yesPrice * 100).toFixed(0)}¢
          </div>
          <div
            className="flex flex-1 items-center justify-center bg-danger/20 text-danger"
          >
            NO {(noPrice * 100).toFixed(0)}¢
          </div>
        </div>
      </div>

      {/* Buy YES / NO toggle */}
      <div className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-bg p-1">
        <button
          type="button"
          onClick={() => setOutcome("yes")}
          disabled={isDisabled}
          className={cn(
            "rounded-lg py-2 text-sm font-bold transition disabled:opacity-50",
            outcome === "yes" ? "bg-primary text-bg" : "text-muted hover:text-text",
          )}
        >
          Buy YES
        </button>
        <button
          type="button"
          onClick={() => setOutcome("no")}
          disabled={isDisabled}
          className={cn(
            "rounded-lg py-2 text-sm font-bold transition disabled:opacity-50",
            outcome === "no" ? "bg-danger text-bg" : "text-muted hover:text-text",
          )}
        >
          Buy NO
        </button>
      </div>

      {/* Amount input */}
      <div className="mt-3">
        <label
          htmlFor={`trading-shares-${slug}`}
          className="text-[11px] font-semibold uppercase tracking-wider text-muted-2"
        >
          Shares
        </label>
        <input
          id={`trading-shares-${slug}`}
          type="number"
          min={1}
          step={1}
          value={amount}
          onChange={(e) =>
            setAmount(Math.max(1, Math.floor(Number(e.target.value) || 1)))
          }
          disabled={isDisabled}
          className="mt-1.5 w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-text focus:border-accent focus:outline-none disabled:opacity-50"
        />
      </div>

      {/* Cost summary */}
      <dl className="mt-3 space-y-1.5 text-xs">
        <div className="flex items-center justify-between">
          <dt className="text-muted">Price</dt>
          <dd className="font-mono font-semibold text-text">${price.toFixed(3)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-muted">Cost</dt>
          <dd className="font-mono font-bold text-primary">{formatUSD(cost)}</dd>
        </div>
        {paperBalance != null && (
          <div className="flex items-center justify-between">
            <dt className="text-muted">Bankroll</dt>
            <dd className="font-mono text-text">{formatUSD(paperBalance)}</dd>
          </div>
        )}
        {maxShares > 0 && (
          <div className="flex items-center justify-between">
            <dt className="text-muted">Max shares</dt>
            <dd className="font-mono text-text">{maxShares.toLocaleString()}</dd>
          </div>
        )}
      </dl>

      <button
        type="button"
        onClick={submit}
        disabled={isDisabled || submitting || amount < 1}
        className={cn(
          "mt-4 w-full rounded-xl py-2.5 text-sm font-bold transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50",
          outcome === "yes" ? "bg-primary text-bg" : "bg-danger text-bg",
        )}
      >
        {isDisabled
          ? "Market closed"
          : submitting
            ? "Placing order…"
            : `Buy ${outcome.toUpperCase()} · ${formatUSD(cost)}`}
      </button>

      {/* Position card when position exists */}
      {!positionLoading && position && (
        <div className="mt-3">
          <PositionCard
            position={position}
            token={token}
            onClosed={() => {
              void refreshBalance();
              void refreshPosition();
            }}
          />
        </div>
      )}

      <p className="mt-2 text-[10px] leading-relaxed text-muted-2">
        Paper simulation only. Prices refresh every 30s.
      </p>
    </div>
  );
}
