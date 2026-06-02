"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  readPortfolio,
  subscribePortfolio,
  resetPortfolio,
  type PortfolioState,
} from "@/lib/portfolio-store";
import {
  buildPaperAccountView,
  selectDisplayedPortfolioState,
  type PaperAccountView,
} from "@/lib/paper-account-view-model";
import { fetchPaperAccount } from "@/lib/paper-trading-api";
import { getMarket, formatUSD, cents, PAPER_BALANCE } from "@/lib/mock-data";
import { Sparkline } from "@/components/Sparkline";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { cn } from "@/lib/cn";

function currentPriceFor(slug: string, outcome: string, side: "YES" | "NO"): number {
  const m = getMarket(slug);
  const oc = m?.outcomes.find((o) => o.label === outcome) ?? m?.outcomes[0];
  const yes = oc?.price ?? 0.5;
  return side === "YES" ? yes : 1 - yes;
}

export default function PortfolioPage() {
  const [state, setState] = useState<PortfolioState>({
    balance: PAPER_BALANCE,
    positions: [],
    history: [],
  });
  const [accountView, setAccountView] = useState<PaperAccountView | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setState(readPortfolio());
    let cancelled = false;
    fetchPaperAccount().then((account) => {
      if (!cancelled && account?.paper_trading_only) {
        setAccountView(buildPaperAccountView(account));
      }
    });
    const unsubscribe = subscribePortfolio(() => setState(readPortfolio()));
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const displayState = useMemo(
    () => selectDisplayedPortfolioState(state, accountView),
    [state, accountView],
  );

  const metrics = useMemo(() => {
    let costBasis = 0;
    let currentValue = 0;
    let wins = 0;
    for (const p of displayState.positions) {
      const cur = currentPriceFor(p.slug, p.outcome, p.side);
      costBasis += p.entryPrice * p.shares;
      currentValue += cur * p.shares;
      if (cur >= p.entryPrice) wins += 1;
    }
    const unrealized = currentValue - costBasis;
    const accountCash = displayState.balance;
    const equity = accountCash + currentValue + (accountView?.reservedCash ?? 0);
    const pnl = equity - PAPER_BALANCE;
    const roi = (pnl / PAPER_BALANCE) * 100;
    const winRate = displayState.positions.length
      ? (wins / displayState.positions.length) * 100
      : 0;
    return { unrealized, equity, pnl, roi, winRate, currentValue };
  }, [displayState, accountView]);

  // Equity curve from history (deterministic-ish reconstruction).
  const equityCurve = useMemo(() => {
    const pts: number[] = [PAPER_BALANCE];
    let running = PAPER_BALANCE;
    for (const h of [...displayState.history].reverse()) {
      running += (currentPriceFor(h.slug, h.outcome, h.side) - h.entryPrice) * h.shares;
      pts.push(running);
    }
    pts.push(metrics.equity);
    return pts.length >= 2 ? pts : [PAPER_BALANCE, PAPER_BALANCE];
  }, [displayState.history, metrics.equity]);

  if (!mounted) {
    return (
      <main className="mx-auto max-w-[1400px] px-4 py-10">
        <div className="skeleton h-40 w-full" />
      </main>
    );
  }

  const openOrders = accountView?.openOrders ?? [];
  const empty = displayState.positions.length === 0 && openOrders.length === 0;

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black text-text">Portfolio</h1>
          <p className="mt-1 text-sm text-muted">Paper-trading positions and P&L.</p>
        </div>
        <button
          onClick={() => resetPortfolio()}
          className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-muted transition hover:text-text"
        >
          Reset paper account
        </button>
      </div>

      {/* Metric cards */}
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Balance" >
          <AnimatedNumber
            value={displayState.balance}
            format={formatUSD}
            className="font-mono text-2xl font-black text-text"
          />
        </MetricCard>
        <MetricCard label="Reserved">
          <AnimatedNumber
            value={accountView?.reservedCash ?? 0}
            format={formatUSD}
            className="font-mono text-2xl font-black text-text"
          />
        </MetricCard>
        <MetricCard label="Equity">
          <AnimatedNumber
            value={metrics.equity}
            format={formatUSD}
            className="font-mono text-2xl font-black text-text"
          />
        </MetricCard>
        <MetricCard label="Total P&L">
          <span
            className={cn(
              "font-mono text-2xl font-black",
              metrics.pnl >= 0 ? "text-primary" : "text-danger",
            )}
          >
            {metrics.pnl >= 0 ? "+" : ""}
            {formatUSD(metrics.pnl)}
          </span>
        </MetricCard>
        <MetricCard label="ROI / Win rate">
          <span
            className={cn(
              "font-mono text-2xl font-black",
              metrics.roi >= 0 ? "text-primary" : "text-danger",
            )}
          >
            {metrics.roi >= 0 ? "+" : ""}
            {metrics.roi.toFixed(2)}%
          </span>
          <span className="ml-2 font-mono text-sm text-muted">
            {metrics.winRate.toFixed(0)}% win
          </span>
        </MetricCard>
      </div>

      {/* Equity curve */}
      <div className="mt-5 rounded-xl border border-border bg-surface p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-text">Equity curve</h2>
          <span className="font-mono text-xs text-muted">since open</span>
        </div>
        <div className="mt-3">
          <Sparkline
            data={equityCurve}
            up={metrics.pnl >= 0}
            width={900}
            height={120}
            className="h-[120px] w-full"
          />
        </div>
      </div>

      {empty ? (
        <div className="mt-5 rounded-xl border border-dashed border-border bg-surface p-10 text-center">
          <p className="text-text">No positions yet.</p>
          <p className="mt-1 text-sm text-muted">
            Place your first paper trade to see it here.
          </p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white transition hover:bg-accent"
          >
            Browse markets
          </Link>
        </div>
      ) : (
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          {openOrders.length ? <OpenOrdersTable orders={openOrders} /> : null}
          {displayState.positions.length ? <PositionsTable state={displayState} /> : null}
          {displayState.history.length ? <HistoryTable state={displayState} /> : null}
        </div>
      )}
    </main>
  );
}

function MetricCard({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-2">
        {label}
      </div>
      <div className="mt-1 flex items-baseline">{children}</div>
    </div>
  );
}

function OpenOrdersTable({ orders }: { orders: PaperAccountView["openOrders"] }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="text-sm font-black text-text">Open backend orders</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-muted-2">
            <tr>
              <th className="pb-2">Market</th>
              <th className="pb-2">Side</th>
              <th className="pb-2 text-right">Remaining</th>
              <th className="pb-2 text-right">Limit</th>
              <th className="pb-2 text-right">Reserved</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id} className="border-t border-border">
                <td className="py-2">
                  <Link href={`/markets/${order.marketSlug}`} className="hover:text-accent">
                    <span className="text-text">{order.marketTitle}</span>
                    <span className="block text-[11px] text-muted">{order.outcome}</span>
                  </Link>
                </td>
                <td className="py-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-mono text-[10px] font-bold",
                      order.outcome === "YES"
                        ? "bg-primary-dim text-primary"
                        : "bg-danger-dim text-danger",
                    )}
                  >
                    {order.side}
                  </span>
                </td>
                <td className="py-2 text-right font-mono text-muted">
                  {order.remainingShares}
                </td>
                <td className="py-2 text-right font-mono text-text">
                  {cents(order.price)}
                </td>
                <td className="py-2 text-right font-mono font-bold text-text">
                  {formatUSD(order.reservedNotional)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PositionsTable({ state }: { state: PortfolioState }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="text-sm font-black text-text">Open positions</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-muted-2">
            <tr>
              <th className="pb-2">Market</th>
              <th className="pb-2">Side</th>
              <th className="pb-2 text-right">Shares</th>
              <th className="pb-2 text-right">Entry</th>
              <th className="pb-2 text-right">Now</th>
              <th className="pb-2 text-right">P&L</th>
            </tr>
          </thead>
          <tbody>
            {state.positions.map((p) => {
              const cur = currentPriceFor(p.slug, p.outcome, p.side);
              const pnl = (cur - p.entryPrice) * p.shares;
              return (
                <tr key={p.id} className="border-t border-border">
                  <td className="py-2">
                    <Link href={`/markets/${p.slug}`} className="hover:text-accent">
                      <span className="text-text">{p.market}</span>
                      <span className="block text-[11px] text-muted">{p.outcome}</span>
                    </Link>
                  </td>
                  <td className="py-2">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 font-mono text-[10px] font-bold",
                        p.side === "YES"
                          ? "bg-primary-dim text-primary"
                          : "bg-danger-dim text-danger",
                      )}
                    >
                      {p.side}
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono text-muted">{p.shares}</td>
                  <td className="py-2 text-right font-mono text-muted">{cents(p.entryPrice)}</td>
                  <td className="py-2 text-right font-mono text-text">{cents(cur)}</td>
                  <td
                    className={cn(
                      "py-2 text-right font-mono font-bold",
                      pnl >= 0 ? "text-primary" : "text-danger",
                    )}
                  >
                    {pnl >= 0 ? "+" : ""}
                    {formatUSD(pnl)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HistoryTable({ state }: { state: PortfolioState }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="text-sm font-black text-text">Trade history</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-muted-2">
            <tr>
              <th className="pb-2">Market</th>
              <th className="pb-2">Side</th>
              <th className="pb-2 text-right">Shares</th>
              <th className="pb-2 text-right">Price</th>
              <th className="pb-2 text-right">Cost</th>
            </tr>
          </thead>
          <tbody>
            {state.history.map((h) => (
              <tr key={h.id} className="border-t border-border">
                <td className="py-2 text-text">{h.market}</td>
                <td className="py-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-mono text-[10px] font-bold",
                      h.side === "YES"
                        ? "bg-primary-dim text-primary"
                        : "bg-danger-dim text-danger",
                    )}
                  >
                    {h.side}
                  </span>
                </td>
                <td className="py-2 text-right font-mono text-muted">{h.shares}</td>
                <td className="py-2 text-right font-mono text-muted">{cents(h.entryPrice)}</td>
                <td className="py-2 text-right font-mono text-text">
                  {formatUSD(h.entryPrice * h.shares)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
