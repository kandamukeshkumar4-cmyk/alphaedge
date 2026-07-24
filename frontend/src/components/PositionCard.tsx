"use client";

import { useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { closePaperPosition } from "@/lib/orders-api";
import { useToast } from "./ToastProvider";

function fmt(v: number) {
  return (v >= 0 ? "+" : "") + v.toFixed(2);
}

function fmtUSD(v: number) {
  return `$${Math.abs(v).toFixed(2)}`;
}

export type Position = {
  market_slug: string;
  outcome: string;
  shares: number;
  avg_cost: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  pnl_pct: number | null;
};

export function PositionCard({
  position,
  token,
  onClosed,
}: {
  position: Position;
  token: string;
  onClosed?: () => void;
}) {
  const { toast } = useToast();
  const [closing, setClosing] = useState(false);
  // One Idempotency-Key per close intent — see TradePanel for the pattern.
  const idemKeyRef = useRef<string | null>(null);

  const currentPrice = position.current_price ?? position.avg_cost;
  const pnl = position.unrealized_pnl ?? 0;
  const pnlPct = position.pnl_pct != null ? position.pnl_pct * 100 : 0;
  const isProfit = pnl >= 0;

  async function closePosition() {
    setClosing(true);
    idemKeyRef.current ??= crypto.randomUUID();
    try {
      const result = await closePaperPosition(
        token,
        {
          slug: position.market_slug,
          outcome: position.outcome.toLowerCase() === "yes" ? "yes" : "no",
          shares: position.shares,
          price: Math.min(Math.max(currentPrice, 0.01), 0.99),
        },
        idemKeyRef.current,
      );
      idemKeyRef.current = null;
      const pnlText = `${result.realized_pnl >= 0 ? "+" : ""}$${result.realized_pnl.toFixed(2)}`;
      toast({ title: "Paper position closed", body: `Paper realized P&L ${pnlText}`, tone: "success" });
      onClosed?.();
    } catch (err) {
      if (!(err instanceof TypeError)) idemKeyRef.current = null;
      toast({
        title: "Paper close failed",
        body: err instanceof Error ? err.message : "Unable to close position",
        tone: "error",
      });
    } finally {
      setClosing(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface-2 p-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wider text-muted-2">
          My Paper Position
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[11px] font-bold",
            position.outcome.toLowerCase() === "yes"
              ? "bg-primary/20 text-primary"
              : "bg-danger/20 text-danger",
          )}
        >
          {position.outcome.toUpperCase()}
        </span>
      </div>

      <dl className="mt-2 space-y-1 text-xs">
        <div className="flex items-center justify-between">
          <dt className="text-muted">Shares</dt>
          <dd className="font-mono font-semibold text-text">
            {position.shares.toFixed(0)}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-muted">Paper avg price</dt>
          <dd className="font-mono text-text">${position.avg_cost.toFixed(3)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-muted">Paper mark</dt>
          <dd className="font-mono text-text">${currentPrice.toFixed(3)}</dd>
        </div>
        <div className="flex items-center justify-between border-t border-border pt-1">
          <dt className="text-muted">Paper unrealized P&L</dt>
          <dd
            className={cn(
              "font-mono font-bold",
              isProfit ? "text-primary" : "text-danger",
            )}
          >
            {fmt(pnl)} ({fmt(pnlPct)}%)
          </dd>
        </div>
      </dl>

      <button
        type="button"
        onClick={closePosition}
        disabled={closing}
        className="mt-3 w-full rounded-lg border border-border py-1.5 text-xs font-semibold text-muted transition hover:border-danger hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
      >
        {closing
          ? "Closing paper…"
          : `Paper sell ${position.shares.toFixed(0)} shares (${fmtUSD(position.shares * currentPrice)})`}
      </button>
    </div>
  );
}
