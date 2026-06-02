"use client";

import { useEffect, useMemo, useState } from "react";
import { formatUSD, cents, type Market } from "@/lib/mock-data";
import { fetchPaperAccount, submitPaperOrder } from "@/lib/paper-trading-api";
import { placeOrder, readPortfolio, subscribePortfolio } from "@/lib/portfolio-store";
import { useToast } from "./ToastProvider";
import { AnimatedNumber } from "./AnimatedNumber";
import { cn } from "@/lib/cn";

export function TradePanel({ market }: { market: Market }) {
  const { toast } = useToast();
  const [outcomeIdx, setOutcomeIdx] = useState(0);
  const [side, setSide] = useState<"YES" | "NO">("YES");
  const [shares, setShares] = useState(10);
  const [balance, setBalance] = useState(100_000);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setBalance(readPortfolio().balance);
    let cancelled = false;
    fetchPaperAccount().then((account) => {
      if (!cancelled && account?.paper_trading_only) {
        setBalance(Number(account.available_cash));
      }
    });
    const unsubscribe = subscribePortfolio(() => setBalance(readPortfolio().balance));
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const outcome = market.outcomes[outcomeIdx];
  const price = side === "YES" ? outcome.price : 1 - outcome.price;
  const preview = useMemo(() => {
    const cost = price * shares;
    const toWin = shares;
    return {
      cost,
      toWin,
      profit: toWin - cost,
      balanceAfter: balance - cost,
    };
  }, [price, shares, balance]);

  const insufficient = preview.cost > balance;

  async function submit() {
    if (shares <= 0) {
      toast({ title: "Enter a quantity", tone: "error" });
      return;
    }
    setSubmitting(true);
    const apiResult = await submitPaperOrder({
      slug: market.slug,
      side,
      shares,
      price,
      forecast: {
        predictedProb: market.forecast.prob,
        confidence: market.forecast.confidence,
        edge: side === "YES" ? market.forecast.edge : -market.forecast.edge,
      },
      currentDrawdown: 0,
      minutesBeforeStart: minutesBeforeStart(market.endsAt),
    });

    if (apiResult.ok) {
      setBalance(Number(apiResult.account.available_cash));
      setSubmitting(false);
      toast({
        title: "Order accepted",
        body: apiResult.message,
        tone: "success",
      });
      return;
    }

    if (apiResult.mode === "api") {
      setSubmitting(false);
      toast({
        title: "Order rejected",
        body: apiResult.message,
        tone: "error",
      });
      return;
    }

    window.setTimeout(() => {
      const res = placeOrder({
        slug: market.slug,
        market: market.title,
        outcome: outcome.label,
        side,
        shares,
        price,
      });
      setSubmitting(false);
      toast({
        title: res.ok ? "Order filled" : "Order rejected",
        body: res.message,
        tone: res.ok ? "success" : "error",
      });
    }, 450);
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      {/* Buy / Sell tabs */}
      <div className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-bg p-1">
        <button
          onClick={() => setSide("YES")}
          className={cn(
            "rounded-md py-2 text-sm font-bold transition",
            side === "YES" ? "bg-primary text-white" : "text-muted hover:text-text",
          )}
        >
          Buy Yes
        </button>
        <button
          onClick={() => setSide("NO")}
          className={cn(
            "rounded-md py-2 text-sm font-bold transition",
            side === "NO" ? "bg-danger text-white" : "text-muted hover:text-text",
          )}
        >
          Buy No
        </button>
      </div>

      {/* Outcome selector for multi-outcome markets */}
      {market.outcomes.length > 2 && (
        <div className="mt-3">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
            Outcome
          </label>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {market.outcomes.map((o, i) => (
              <button
                key={o.id}
                onClick={() => setOutcomeIdx(i)}
                className={cn(
                  "rounded-md border px-2 py-1 text-xs font-semibold transition",
                  i === outcomeIdx
                    ? "border-accent bg-surface-2 text-text"
                    : "border-border text-muted hover:text-text",
                )}
              >
                {o.emoji} {o.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Price chips */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div
          className={cn(
            "rounded-lg border p-2.5 text-center",
            side === "YES" ? "border-primary/50 bg-primary-dim" : "border-border",
          )}
        >
          <div className="text-[11px] font-semibold text-muted">Yes</div>
          <div className="font-mono text-lg font-black text-primary">
            {cents(outcome.price)}
          </div>
        </div>
        <div
          className={cn(
            "rounded-lg border p-2.5 text-center",
            side === "NO" ? "border-danger/50 bg-danger-dim" : "border-border",
          )}
        >
          <div className="text-[11px] font-semibold text-muted">No</div>
          <div className="font-mono text-lg font-black text-danger">
            {cents(1 - outcome.price)}
          </div>
        </div>
      </div>

      {/* Shares */}
      <div className="mt-3">
        <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
          Shares
        </label>
        <div className="mt-1.5 flex items-center gap-2">
          <input
            type="number"
            min={0}
            value={shares}
            onChange={(e) => setShares(Math.max(0, Number(e.target.value)))}
            className="w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-text focus:border-accent focus:outline-none"
          />
          {[10, 50, 100].map((q) => (
            <button
              key={q}
              onClick={() => setShares(q)}
              className="rounded-md border border-border px-2 py-2 text-xs font-semibold text-muted transition hover:text-text"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Preview */}
      <dl className="mt-4 space-y-2 text-sm">
        <Row label="Avg price" value={cents(price)} />
        <Row label="Cost" value={formatUSD(preview.cost)} />
        <Row label="To win" value={formatUSD(preview.toWin)} accent />
        <Row
          label="Potential profit"
          value={`${preview.profit >= 0 ? "+" : ""}${formatUSD(preview.profit)}`}
          accent
        />
      </dl>

      <button
        onClick={submit}
        disabled={submitting || insufficient}
        className={cn(
          "mt-4 w-full rounded-lg py-2.5 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50",
          side === "YES"
            ? "bg-primary text-white hover:bg-accent"
            : "bg-danger text-white hover:bg-[#ff5d67]",
        )}
      >
        {submitting
          ? "Processing…"
          : insufficient
            ? "Insufficient balance"
            : `Buy ${side} · ${outcome.label}`}
      </button>

      <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-muted">
        <span>Paper balance</span>
        <AnimatedNumber
          value={balance}
          format={(n) => formatUSD(n)}
          className="font-mono font-bold text-text"
        />
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted-2">
        Paper simulation only.
      </p>
    </div>
  );
}

function minutesBeforeStart(iso: string): number {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.floor(ms / 60_000));
}

function Row({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className={cn("font-mono font-bold", accent ? "text-primary" : "text-text")}>
        {value}
      </dd>
    </div>
  );
}
