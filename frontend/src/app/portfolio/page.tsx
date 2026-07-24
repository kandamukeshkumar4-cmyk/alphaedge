"use client";

import { marketHref } from "@/lib/market-href";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { LivePricesProvider, useLivePrice } from "@/context/live-prices";

import { useAuth } from "@/hooks/useAuth";
import { AnalystChatDrawer } from "@/components/AnalystChatDrawer";
import { ExposurePanel } from "@/components/ExposurePanel";
import { PortfolioClvPanel } from "@/components/PortfolioClvPanel";
import { PortfolioRiskPanel } from "@/components/PortfolioRiskPanel";
import { PortfolioAnalyticsPanel } from "@/components/portfolio/PortfolioAnalyticsPanel";
import { TraderProfileCard } from "@/components/TraderProfileCard";
import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { formatUSD } from "@/lib/mock-data";
import {
  fetchOrderHistory,
  fetchPortfolio,
  getAccessToken,
  type OrderHistoryItem,
  type PortfolioPosition,
  type PortfolioView,
} from "@/lib/portfolio-api";
import { PageHeader, PageShell } from "@/components/ui/kit";

export default function PortfolioPage() {
  const router = useRouter();
  const { token, isReady } = useAuth();
  const [portfolio, setPortfolio] = useState<PortfolioView | null>(null);
  const [history, setHistory] = useState<OrderHistoryItem[]>([]);
  const [activeTab, setActiveTab] = useState<"positions" | "history" | "analytics">(
    "positions",
  );
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (isReady && !token) {
      router.replace("/auth/login?next=/portfolio");
    }
  }, [isReady, token, router]);

  useEffect(() => {
    setMounted(true);
    if (token) {
      void loadPortfolio();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadPortfolio() {
    setLoading(true);
    setError(null);
    const token = getAccessToken();
    if (!token) {
      setPortfolio(null);
      setError("Log in to view your paper portfolio.");
      setLoading(false);
      return;
    }
    if (!API_BASE) {
      setPortfolio(null);
      setError("Set NEXT_PUBLIC_API_URL to load your portfolio.");
      setLoading(false);
      return;
    }
    try {
      const next = await fetchPortfolio(token);
      setPortfolio(next);
      await loadHistory(token);
    } catch (err) {
      setPortfolio(null);
      setHistory([]);
      setError(err instanceof Error ? err.message : "Failed to load portfolio.");
    } finally {
      setLoading(false);
    }
  }

  async function loadHistory(tokenOverride?: string) {
    const authToken = tokenOverride ?? getAccessToken();
    if (!authToken || !API_BASE) {
      setHistory([]);
      return;
    }
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const rows = await fetchOrderHistory(authToken);
      setHistory(rows);
    } catch (err) {
      setHistory([]);
      setHistoryError(
        err instanceof Error ? err.message : "Failed to load trade history.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  if (!mounted || !isReady || !token) {
    return (
      <main className="mx-auto max-w-[1200px] px-4 py-10">
        <div className="skeleton h-40 w-full" />
      </main>
    );
  }

  const empty = !loading && portfolio !== null && portfolio.positions.length === 0;

  // H-PERF-01: one shared multiplexed feed for every open position instead of a
  // WebSocket per row. Priority = the open-position slugs.
  const livePriceSlugs =
    portfolio?.positions.filter((p) => !p.settled).map((p) => p.market_slug) ?? [];

  return (
    <LivePricesProvider markets={[]} prioritySlugs={livePriceSlugs}>
    <PageShell width="medium">
      <PageHeader
        kicker="Unified paper portfolio"
        title="Portfolio"
        subtitle="Gross desk performance — paper balance, open positions, and risk across every market type."
        actions={
          <button
            type="button"
            onClick={() => void loadPortfolio()}
            disabled={loading}
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        }
      />

      {error ? (
        <section className="mb-6 rounded-2xl border border-border bg-surface p-5 text-sm text-muted">
          <p>{error}</p>
          {!getAccessToken() ? (
            <p className="mt-3">
              <Link href="/auth/login" className="font-semibold text-accent hover:underline">
                Log in
              </Link>{" "}
              or{" "}
              <Link href="/auth/signup" className="font-semibold text-accent hover:underline">
                create an account
              </Link>
              .
            </p>
          ) : null}
        </section>
      ) : null}

      {portfolio ? (
        <>
          <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Portfolio value"
              value={formatUSD(portfolio.portfolio_value)}
            />
            <MetricCard label="Paper balance" value={formatUSD(portfolio.paper_balance)} />
            <MetricCard
              label="Unrealized P&amp;L"
              value={formatSignedUsd(portfolio.unrealized_pnl)}
              tone={portfolio.unrealized_pnl >= 0 ? "positive" : "negative"}
            />
            <MetricCard
              label="Realized P&amp;L"
              value={formatSignedUsd(portfolio.realized_pnl)}
              tone={portfolio.realized_pnl >= 0 ? "positive" : "negative"}
            />
          </section>

          <PortfolioClvPanel token={token} />

          {token ? <ExposurePanel token={token} /> : null}

          {token ? <TraderProfileCard token={token} /> : null}

          {token ? <PortfolioRiskPanel token={token} /> : null}

          <AnalystChatDrawer context="portfolio" />

          <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3">
              <button
                type="button"
                onClick={() => setActiveTab("positions")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-bold transition",
                  activeTab === "positions"
                    ? "bg-accent text-bg"
                    : "text-muted hover:text-text",
                )}
              >
                Positions
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("history")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-bold transition",
                  activeTab === "history"
                    ? "bg-accent text-bg"
                    : "text-muted hover:text-text",
                )}
              >
                Trade History
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("analytics")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-bold transition",
                  activeTab === "analytics"
                    ? "bg-accent text-bg"
                    : "text-muted hover:text-text",
                )}
                data-testid="portfolio-tab-analytics"
              >
                Analytics
              </button>
            </div>

            {activeTab === "positions" ? (
              empty ? (
                <div className="py-10 text-center">
                  <p className="text-lg font-semibold text-text">No paper trades yet</p>
                  <p className="mt-2 text-sm text-muted">
                    Place a paper trade on a market to see positions here.
                  </p>
                  <Link
                    href="/markets"
                    className="mt-5 inline-block rounded-xl bg-accent px-4 py-2 text-sm font-bold text-bg transition hover:brightness-110"
                  >
                    Browse markets
                  </Link>
                </div>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-[11px] uppercase tracking-wider text-muted-2">
                      <tr>
                        <th className="pb-2">Market</th>
                        <th className="pb-2">Side</th>
                        <th className="pb-2 text-right">Quantity</th>
                        <th className="pb-2 text-right">Entry</th>
                        <th className="pb-2 text-right">Mark</th>
                        <th className="pb-2 text-right">Unrealized</th>
                        <th className="pb-2 text-right">Realized</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.positions.map((position) => (
                        <PortfolioPositionRow key={position.id} position={position} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : activeTab === "analytics" ? (
              <div className="mt-4">
                <PortfolioAnalyticsPanel token={token} />
              </div>
            ) : historyError ? (
              <p className="mt-4 text-sm text-muted">{historyError}</p>
            ) : historyLoading ? (
              <p className="mt-4 text-sm text-muted">Loading trade history…</p>
            ) : history.length === 0 ? (
              <p className="mt-4 text-sm text-muted">No trades yet.</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-[11px] uppercase tracking-wider text-muted-2">
                    <tr>
                      <th className="pb-2">Market</th>
                      <th className="pb-2">Outcome</th>
                      <th className="pb-2 text-right">Shares</th>
                      <th className="pb-2 text-right">Price</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2 text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((trade, index) => (
                      <tr
                        key={`${trade.slug}-${trade.created_at}-${index}`}
                        className="border-t border-border"
                      >
                        <td className="max-w-[200px] py-2">
                          <Link
                            href={marketHref(trade.slug)}
                            title={trade.slug}
                            className="block truncate text-text hover:text-accent"
                          >
                            {trade.slug}
                          </Link>
                        </td>
                        <td className="py-2 uppercase text-muted">{trade.outcome}</td>
                        <td className="py-2 text-right font-mono text-muted">
                          {trade.shares}
                        </td>
                        <td className="py-2 text-right font-mono text-text">
                          {formatUSD(trade.price)}
                        </td>
                        <td className="py-2">
                          {trade.settled ? (
                            <span className="font-semibold text-primary">Settled ✓</span>
                          ) : (
                            <span className="text-muted">Open</span>
                          )}
                        </td>
                        <td className="py-2 text-right font-mono text-[11px] text-muted">
                          {formatTradeDate(trade.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}

      <footer className="mt-8 rounded-2xl border border-border bg-surface p-4 text-xs leading-relaxed text-muted">
        {portfolio?.disclaimer ??
          "Research only — not financial advice. Verify resolution terms. Paper trading only."}
      </footer>
    </PageShell>
    </LivePricesProvider>
  );
}

function PortfolioPositionRow({ position }: { position: PortfolioPosition }) {
  const live = useLivePrice(
    position.settled ? "" : position.market_slug,
    position.current_price ?? position.price ?? 0,
  );
  const markPrice = useMemo(() => {
    if (position.settled) {
      return null;
    }
    if (live.connected && live.yes > 0) {
      return position.outcome.toLowerCase() === "yes" ? live.yes : live.no;
    }
    return position.current_price ?? position.price;
  }, [live.connected, live.no, live.yes, position]);

  const unrealized =
    position.settled || markPrice === null || position.price === null
      ? 0
      : position.quantity * (markPrice - position.price);

  return (
    <tr
      className={cn(
        "border-t border-border",
        position.settled && "opacity-60",
      )}
    >
      <td className="py-2">
        <Link href={marketHref(position.market_slug)} className="hover:text-accent">
          <span className="flex items-center gap-1.5 text-text">
            {position.settled ? <span aria-hidden>✓</span> : null}
            {position.market_title}
          </span>
          <span className="block text-[11px] text-muted">
            {position.outcome}
            {position.settlement_status === "locked_unsettled" ? " · Locked, unsettled" : ""}
          </span>
        </Link>
      </td>
      <td className="py-2">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase",
            position.outcome.toLowerCase() === "yes"
              ? "bg-primary-dim text-primary"
              : "bg-danger-dim text-danger",
          )}
        >
          {position.side}
        </span>
      </td>
      <td className="py-2 text-right font-mono text-muted">{position.quantity}</td>
      <td className="py-2 text-right font-mono text-text">
        {position.price === null ? "—" : formatUSD(position.price)}
      </td>
      <td className="py-2 text-right font-mono text-text">
        {markPrice === null ? "—" : formatUSD(markPrice)}
      </td>
      <td
        className={cn(
          "py-2 text-right font-mono font-bold",
          unrealized >= 0 ? "text-primary" : "text-danger",
        )}
      >
        {position.settled ? "—" : formatSignedUsd(unrealized)}
      </td>
      <td
        className={cn(
          "py-2 text-right font-mono font-bold",
          (position.realized_pnl ?? 0) >= 0 ? "text-primary" : "text-danger",
        )}
      >
        {position.realized_pnl === null || position.realized_pnl === undefined
          ? "—"
          : formatSignedUsd(position.realized_pnl)}
      </td>
    </tr>
  );
}

function MetricCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">{label}</p>
      <p
        className={cn(
          "mt-2 font-mono text-2xl font-black",
          tone === "positive"
            ? "text-primary"
            : tone === "negative"
              ? "text-danger"
              : "text-text",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function formatSignedUsd(value: number): string {
  const formatted = formatUSD(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

function formatTradeDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
