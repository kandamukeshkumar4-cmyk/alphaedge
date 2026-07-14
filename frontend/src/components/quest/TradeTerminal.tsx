"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { TabList, Tab } from "@astryxdesign/core/TabList";
import { ChartDrawingToolbar } from "@/components/quest/ChartDrawingToolbar";
import { DecisionCard } from "@/components/DecisionCard";
import { PriceChart } from "@/components/PriceChartLazy";
import { OrderBook } from "@/components/OrderBook";
import { MarketTradingPanel } from "@/components/MarketTradingPanel";
import { useAtlasPanel } from "@/context/atlas-panel";
import { useAuth } from "@/hooks/useAuth";
import { API_BASE, fetchMarkets, fetchMarketDetail, hasLiveApi } from "@/lib/alphaedge-api";
import { fetchOrderHistory, fetchPortfolio, type OrderHistoryItem } from "@/lib/portfolio-api";
import { formatCompactUSD, getMarket, type Market } from "@/lib/mock-data";
import { marketHref } from "@/lib/market-href";
import { marketLifecycle, marketLifecycleLabel } from "@/lib/market-lifecycle";
import { cn } from "@/lib/cn";

type ReportTab =
  | "positions"
  | "balances"
  | "open-orders"
  | "trade-history"
  | "order-history";

type FeedTab = "for-you" | "this-market" | "following" | "news";

const REPORT_TABS: { id: ReportTab; label: string }[] = [
  { id: "positions", label: "Positions" },
  { id: "balances", label: "Balances" },
  { id: "open-orders", label: "Open Orders" },
  { id: "trade-history", label: "Trade History" },
  { id: "order-history", label: "Order History" },
];

const FALLBACK_MARKET = getMarket("nba-2025-01-15-lal-bos") ?? null;
const LIVE_API = hasLiveApi();

export function TradeTerminal({ initialSlug }: { initialSlug?: string }) {
  const { token, paperBalance } = useAuth();
  const { openPanel, setMarket } = useAtlasPanel();
  // Prefer empty/loading when a live API is configured — never paint the seed
  // Lakers market as if it were production data.
  const [markets, setMarkets] = useState<Market[]>([]);
  const [slug, setSlug] = useState(initialSlug ?? "");
  const [market, setMarketState] = useState<Market | null>(null);
  const [loadingMarkets, setLoadingMarkets] = useState(LIVE_API);
  const [rightTab, setRightTab] = useState<"book" | "trades">("book");
  const [panelTab, setPanelTab] = useState<"trade" | "chat">("trade");
  const [reportTab, setReportTab] = useState<ReportTab>("order-history");
  const [feedTab, setFeedTab] = useState<FeedTab>("this-market");
  const [drawTool, setDrawTool] = useState("cursor");
  const [orders, setOrders] = useState<OrderHistoryItem[]>([]);
  const [positions, setPositions] = useState<
    { market_slug: string; outcome: string; quantity: number; unrealized_pnl?: number | null }[]
  >([]);

  useEffect(() => {
    let dead = false;
    setLoadingMarkets(true);
    fetchMarkets({})
      .then((rows) => {
        if (dead) return;
        const live = rows.filter((m) => m.slug.startsWith("pm-") || m.slug.startsWith("ks-"));
        const list =
          live.length > 0
            ? live
            : rows.length > 0
              ? rows
              : FALLBACK_MARKET
                ? [FALLBACK_MARKET]
                : [];
        // Prefer open markets — API volume sort often puts resolved 0¢ markets first,
        // which makes Trade look empty (flat chart, empty book).
        const openFirst = [
          ...list.filter((m) => m.status === "open" || m.status == null),
          ...list.filter((m) => m.status === "locked"),
          ...list.filter((m) => m.status === "resolved"),
        ];
        const ordered = openFirst.length > 0 ? openFirst : list;
        setMarkets(ordered);
        const pick =
          (initialSlug && ordered.find((m) => m.slug === initialSlug)) ||
          (initialSlug && rows.find((m) => m.slug === initialSlug)) ||
          ordered[0] ||
          FALLBACK_MARKET;
        if (pick) {
          setSlug(pick.slug);
          setMarketState(pick);
        }
      })
      .catch(() => {
        // Offline / API down: seed only as last resort, and only if no slug was requested.
        if (dead) return;
        if (FALLBACK_MARKET && !initialSlug) {
          setMarkets([FALLBACK_MARKET]);
          setSlug(FALLBACK_MARKET.slug);
          setMarketState(FALLBACK_MARKET);
        }
      })
      .finally(() => {
        if (!dead) setLoadingMarkets(false);
      });
    return () => {
      dead = true;
    };
  }, [initialSlug]);

  useEffect(() => {
    if (!slug) return;
    let dead = false;
    fetchMarketDetail(slug).then((m) => {
      if (!dead && m) setMarketState(m);
    });
    setMarket(slug, market?.title ?? null);
    return () => {
      dead = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync ATLAS context on slug
  }, [slug]);

  const loadReports = useCallback(async () => {
    if (!token) {
      setOrders([]);
      setPositions([]);
      return;
    }
    try {
      const [hist, port] = await Promise.all([
        fetchOrderHistory(token, { apiBase: API_BASE }),
        fetchPortfolio(token, { apiBase: API_BASE }),
      ]);
      setOrders(hist);
      setPositions(
        port.positions
          .filter((p) => !p.settled)
          .map((p) => ({
            market_slug: p.market_slug,
            outcome: p.outcome,
            quantity: p.quantity,
            unrealized_pnl: p.unrealized_pnl,
          })),
      );
    } catch {
      setOrders([]);
      setPositions([]);
    }
  }, [token]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  const yesPct = Math.round((market?.outcomes[0]?.price ?? 0.5) * 1000) / 10;
  const lifecycle = market ? marketLifecycle(market) : null;

  const picker = useMemo(() => markets.slice(0, 40), [markets]);

  return (
    <div className="flex h-[calc(100vh-7.5rem)] min-h-[640px] flex-col">
      {/* Market header */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-lg font-bold text-text sm:text-xl">
              {loadingMarkets
                ? "Loading live markets…"
                : (market?.title ?? "Select a market")}
            </h1>
            <select
              className="max-w-[220px] rounded-lg border border-border bg-surface px-2 py-1 text-xs text-muted"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              aria-label="Select market"
            >
              {picker.map((m) => (
                <option key={m.slug} value={m.slug}>
                  {m.title}
                </option>
              ))}
            </select>
          </div>
          <p className="mt-1 flex flex-wrap gap-3 text-[11px] text-muted-2">
            <span>Liquidity: {formatCompactUSD((market?.volume ?? 0) * 0.35)}</span>
            <span>Volume: {formatCompactUSD(market?.volume ?? 0)}</span>
            {market?.endsAt ? <span>End: {market.endsAt}</span> : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <p className="font-mono text-2xl font-black tabular-nums text-primary">{yesPct}%</p>
          <button
            type="button"
            onClick={() =>
              openPanel({
                mode: "analyze",
                marketSlug: slug,
                marketTitle: market?.title ?? null,
                seedPrompt: `Deep-dive ${market?.title ?? slug} for a paper trade. Current YES ${yesPct}%.`,
              })
            }
            className="rounded-lg border border-primary/40 bg-primary-dim px-3 py-2 text-sm font-bold text-primary shadow-glow transition hover:bg-primary hover:text-bg"
          >
            ✦ AI Analyze
          </button>
        </div>
      </div>

      {/* Main 3-pane */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[200px_minmax(0,1fr)_300px]">
        {/* Left feed */}
        <aside className="hidden border-r border-border lg:flex lg:flex-col">
          <div className="flex gap-0.5 border-b border-border px-2 pt-2">
            {(
              [
                ["for-you", "For You"],
                ["this-market", "This Market"],
                ["following", "Following"],
                ["news", "News"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setFeedTab(id)}
                className={cn(
                  "flex-1 truncate px-1 py-2 text-[10px] font-bold transition",
                  feedTab === id ? "text-primary" : "text-muted hover:text-text",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <p className="text-center text-xs text-muted-2">
              {feedTab === "this-market"
                ? "No quests for this market yet."
                : "Feed empty — open AI Analyze to start a brief."}
            </p>
          </div>
        </aside>

        {/* Chart */}
        <section className="min-w-0 border-r border-border p-3">
          <div className="mb-2.5 flex flex-wrap items-end justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <p className="font-mono text-[22px] font-black leading-none tracking-tight text-text sm:text-[26px]">
                  {yesPct.toFixed(1)}% Chance
                </p>
                <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-[11px] font-bold text-muted">
                  Last {Math.round(yesPct)}¢
                </span>
                <span className="text-[12px] text-muted">
                  — {market?.outcomes[0]?.label ?? "YES"} / {market?.outcomes[1]?.label ?? "NO"}
                </span>
              </div>
              <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-2">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      lifecycle === "live" ? "animate-pulse bg-primary" : "bg-muted-2",
                    )}
                  />
                  Paper · {lifecycle ? marketLifecycleLabel(lifecycle).toLowerCase() : "loading"}
                </span>
                <span>·</span>
                <span>2 outcomes</span>
                {market?.category ? (
                  <>
                    <span>·</span>
                    <span className="uppercase tracking-wide">{market.category}</span>
                  </>
                ) : null}
              </p>
            </div>
            {market ? (
              <Link href={marketHref(market.slug)} className="text-[11px] font-semibold text-muted hover:text-primary">
                Full detail →
              </Link>
            ) : null}
          </div>
          {market ? (
            <div className="relative h-[min(420px,48vh)] overflow-hidden rounded-xl border border-border bg-surface">
              <ChartDrawingToolbar active={drawTool} onSelect={setDrawTool} />
              <div className="h-full pl-10">
                <PriceChart
                  slug={market.slug}
                  live={lifecycle === "live"}
                  endPrice={market.outcomes[0]?.price ?? 0.5}
                  height={380}
                />
              </div>
            </div>
          ) : (
            <div className="skeleton h-[min(420px,48vh)] w-full rounded-xl" />
          )}
        </section>

        {/* Right: book + trade/chat */}
        <aside className="flex min-h-0 flex-col overflow-hidden">
          <div className="flex border-b border-border">
            {(
              [
                ["book", "Order Book"],
                ["trades", "Trades"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setRightTab(id)}
                className={cn(
                  "flex-1 py-2.5 text-xs font-bold transition",
                  rightTab === id
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted hover:text-text",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="max-h-[200px] overflow-y-auto border-b border-border p-2">
            {rightTab === "book" && market ? (
              <div className="[&>div]:rounded-lg [&>div]:border-0 [&>div]:bg-transparent [&>div]:p-0">
                <OrderBook market={market} />
              </div>
            ) : (
              <p className="py-6 text-center text-xs text-muted-2">No recent trades.</p>
            )}
          </div>

          <div className="flex border-b border-border">
            {(
              [
                ["trade", "Trade"],
                ["chat", "Chat"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => {
                  setPanelTab(id);
                  if (id === "chat") {
                    openPanel({
                      mode: "chat",
                      marketSlug: slug,
                      marketTitle: market?.title ?? null,
                    });
                  }
                }}
                className={cn(
                  "flex-1 py-2.5 text-xs font-bold transition",
                  panelTab === id
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted hover:text-text",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {panelTab === "chat" ? (
              <div className="space-y-3 p-2">
                <p className="text-xs text-muted">
                  Chat opens in the ATLAS rail. Analysis only — no order placement.
                </p>
                <button
                  type="button"
                  onClick={() =>
                    openPanel({
                      mode: "chat",
                      marketSlug: slug,
                      marketTitle: market?.title ?? null,
                      seedPrompt: `What is the paper edge on ${market?.title ?? slug}?`,
                    })
                  }
                  className="w-full rounded-lg bg-primary py-2.5 text-sm font-bold text-bg"
                >
                  Open ATLAS Chat
                </button>
              </div>
            ) : market ? (
              <div className="space-y-3 [&>div]:rounded-lg [&>div]:border-border">
                <MarketTradingPanel
                  slug={market.slug}
                  title={market.title}
                  initialYesPrice={market.outcomes[0]?.price ?? 0.5}
                />
                {/* P08: reuse the advisory DecisionCard (verdict + edge + CLV gate)
                    on the primary trade surface — analysis only, no order path. */}
                <DecisionCard slug={market.slug} />
              </div>
            ) : (
              <div className="skeleton h-48 w-full rounded-lg" />
            )}
          </div>
        </aside>
      </div>

      {/* Bottom reports */}
      <div className="border-t border-border bg-surface">
        <div className="flex items-center gap-2 overflow-x-auto px-3 pt-2">
          <TabList
            value={reportTab}
            onChange={(v) => setReportTab(v as ReportTab)}
            size="sm"
            hasDivider
          >
            {REPORT_TABS.map((t) => (
              <Tab key={t.id} value={t.id} label={t.label} />
            ))}
          </TabList>
          <div className="ml-auto flex gap-2 pb-1">
            <span className="rounded border border-border px-2 py-0.5 text-[10px] font-bold text-muted">
              Polymarket
            </span>
            <span className="rounded border border-border px-2 py-0.5 text-[10px] font-bold text-muted-2">
              Kalshi
            </span>
          </div>
        </div>
        <div className="max-h-36 overflow-y-auto px-4 py-3">
          <ReportBody
            tab={reportTab}
            orders={orders}
            positions={positions}
            balance={paperBalance}
            loggedIn={!!token}
          />
        </div>
      </div>
    </div>
  );
}

function ReportBody({
  tab,
  orders,
  positions,
  balance,
  loggedIn,
}: {
  tab: ReportTab;
  orders: OrderHistoryItem[];
  positions: { market_slug: string; outcome: string; quantity: number; unrealized_pnl?: number | null }[];
  balance: number | null;
  loggedIn: boolean;
}) {
  if (!loggedIn) {
    return (
      <p className="text-sm text-muted-2">
        Log in to see paper {tab.replace("-", " ")}.{" "}
        <Link href="/auth/login" className="text-primary hover:underline">
          Log in
        </Link>
      </p>
    );
  }

  if (tab === "balances") {
    return (
      <p className="font-mono text-sm text-text">
        Available:{" "}
        <span className="font-bold text-primary">
          {balance != null ? `$${balance.toFixed(2)}` : "—"}
        </span>{" "}
        <span className="text-muted-2">(simulated)</span>
      </p>
    );
  }

  if (tab === "positions") {
    if (positions.length === 0) {
      return <p className="text-sm text-muted-2">No open positions.</p>;
    }
    return (
      <ul className="space-y-1.5">
        {positions.map((p) => (
          <li
            key={`${p.market_slug}-${p.outcome}`}
            className="flex justify-between font-mono text-xs text-text"
          >
            <span>
              {p.market_slug} · {p.outcome.toUpperCase()} ×{p.quantity}
            </span>
            <span className={cn((p.unrealized_pnl ?? 0) >= 0 ? "text-primary" : "text-danger")}>
              {p.unrealized_pnl != null ? `$${p.unrealized_pnl.toFixed(2)}` : "—"}
            </span>
          </li>
        ))}
      </ul>
    );
  }

  if (orders.length === 0) {
    return (
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-sm text-muted-2"
      >
        No open orders.
      </motion.p>
    );
  }

  return (
    <ul className="space-y-1.5">
      {orders.slice(0, 12).map((o, i) => (
        <li
          key={`${o.slug}-${o.created_at}-${i}`}
          className="flex justify-between font-mono text-xs text-muted"
        >
          <span>
            {o.slug} · {o.side} {o.outcome}
          </span>
          <span className="text-text">
            {o.shares} @ {Math.round(o.price * 100)}¢
          </span>
        </li>
      ))}
    </ul>
  );
}
