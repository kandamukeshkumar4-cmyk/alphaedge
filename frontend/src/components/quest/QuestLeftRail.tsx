"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/leaderboard-api";
import {
  fetchSignalsDashboard,
  type SignalFeedItem,
} from "@/lib/signals-dashboard-api";
import { useLivePrice } from "@/context/live-prices";
import { cn } from "@/lib/cn";
import { marketHref } from "@/lib/market-href";
import { formatCompactUSD, type Market } from "@/lib/mock-data";
import { DEMO_LEADERBOARD, DEMO_SIGNALS } from "@/lib/demo-data";
import { DemoChip } from "@/components/quest/DemoChip";

const RANK_COLORS = ["text-gold", "text-muted", "text-[#c9825a]"];

function RailSection({
  title,
  href,
  demo,
  children,
}: {
  title: string;
  href: string;
  demo?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-surface">
      <Link
        href={href}
        className="flex items-center justify-between gap-2 px-2.5 py-2 text-xs font-semibold text-text hover:text-accent-bright"
      >
        <span className="flex items-center gap-1.5">
          {title}
          {demo && <DemoChip />}
        </span>
        <span className="text-muted-2">›</span>
      </Link>
      <div className="px-1 pb-1.5">{children}</div>
    </section>
  );
}

function TrendingRow({ market, rank }: { market: Market; rank: number }) {
  const live = useLivePrice(market.slug, market.outcomes[0]?.price ?? 0.5);
  const up = live.deltaPts >= 0;
  return (
    <Link
      href={marketHref(market.slug)}
      className="flex items-center gap-2 rounded-md px-1.5 py-1.5 hover:bg-surface-2"
    >
      <span className={cn("w-3.5 font-mono text-[11px] font-bold", RANK_COLORS[rank] ?? "text-muted-2")}>
        {rank + 1}
      </span>
      <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-text">
        {market.title}
      </span>
      <span className="text-right">
        <span className="block font-mono text-[11px] font-semibold tabular-nums text-text">
          {Math.round(live.price * 100)}¢
        </span>
        <span className={cn("block font-mono text-[9px]", up ? "text-primary" : "text-danger")}>
          {up ? "↗ +" : "↘ "}
          {live.deltaPts}pt
        </span>
      </span>
    </Link>
  );
}

export function QuestLeftRail({ trending }: { trending: Market[] }) {
  const [traders, setTraders] = useState<LeaderboardEntry[]>([]);
  const [signals, setSignals] = useState<SignalFeedItem[]>([]);
  const [tradersDemo, setTradersDemo] = useState(false);
  const [signalsDemo, setSignalsDemo] = useState(false);

  useEffect(() => {
    fetchLeaderboard()
      .then((rows) => {
        if (rows.length > 0) setTraders(rows.slice(0, 5));
        else {
          setTraders(DEMO_LEADERBOARD);
          setTradersDemo(true);
        }
      })
      .catch(() => {
        setTraders(DEMO_LEADERBOARD);
        setTradersDemo(true);
      });
    fetchSignalsDashboard()
      .then((d) => {
        const rows = (d?.signals ?? []).slice(0, 5);
        if (rows.length > 0) setSignals(rows);
        else {
          setSignals(DEMO_SIGNALS);
          setSignalsDemo(true);
        }
      })
      .catch(() => {
        setSignals(DEMO_SIGNALS);
        setSignalsDemo(true);
      });
  }, []);

  const [platform, setPlatform] = useState<"kalshi" | "polymarket">("kalshi");
  const trendingForPlatform = trending.filter(
    (m) => !m.source || m.source === platform,
  );
  const trendingList =
    trendingForPlatform.length > 0 ? trendingForPlatform : trending;

  return (
    <aside className="no-scrollbar flex w-full flex-col gap-2 lg:sticky lg:top-12 lg:max-h-[calc(100vh-3.5rem)] lg:w-[190px] lg:shrink-0 lg:self-start lg:overflow-y-auto">
      <div className="flex gap-0.5 rounded-lg border border-border bg-surface p-0.5">
        {(["kalshi", "polymarket"] as const).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPlatform(p)}
            className={cn(
              "flex-1 rounded-md px-1.5 py-1 text-[11px] font-semibold capitalize transition",
              platform === p
                ? "bg-surface-3 text-text"
                : "text-muted hover:text-text",
            )}
          >
            {p}
          </button>
        ))}
      </div>

      <RailSection title="Top Traders" href="/leaderboard" demo={tradersDemo}>
        {traders.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-2">Paper-trading ranks appear here.</p>
        ) : (
          traders.map((t, i) => (
            <Link
              key={t.rank}
              href="/leaderboard"
              className="flex items-center gap-2 rounded-md px-1.5 py-1.5 hover:bg-surface-2"
            >
              <span className={cn("w-3.5 font-mono text-[11px] font-bold", RANK_COLORS[i] ?? "text-muted-2")}>
                {t.rank}
              </span>
              <span className="grid h-5 w-5 place-items-center rounded-full bg-surface-3 text-[9px] font-bold text-muted">
                {t.username.slice(0, 2).toUpperCase()}
              </span>
              <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-text">
                {t.username}
              </span>
              <span
                className={cn(
                  "font-mono text-[11px] font-semibold",
                  t.realized_pnl >= 0 ? "text-primary" : "text-danger",
                )}
              >
                {t.realized_pnl >= 0 ? "+" : ""}
                {formatCompactUSD(t.realized_pnl)}
              </span>
            </Link>
          ))
        )}
      </RailSection>

      <RailSection title="Trending Markets" href="/markets">
        {trendingList.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-2">Loading live markets…</p>
        ) : (
          trendingList
            .slice(0, 5)
            .map((m, i) => <TrendingRow key={m.id} market={m} rank={i} />)
        )}
      </RailSection>

      <RailSection title="Live Signals" href="/signals" demo={signalsDemo}>
        {signals.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-2">
            Whale moves and edge alerts show up here automatically.
          </p>
        ) : (
          signals.map((s) => (
            <Link
              key={s.id}
              href="/signals"
              className="flex items-center gap-1.5 rounded-md px-1.5 py-1.5 hover:bg-surface-2"
            >
              <span
                className={cn(
                  "shrink-0 rounded px-1 py-0.5 text-[8px] font-bold uppercase",
                  s.is_edge ? "bg-primary-dim text-primary" : "bg-surface-3 text-muted",
                )}
              >
                {s.signal_type.replaceAll("_", " ").slice(0, 10)}
              </span>
              <span className="min-w-0 flex-1 truncate text-[11px] text-text">{s.market_name}</span>
              {s.implied_edge != null && (
                <span className="font-mono text-[9px] font-semibold text-accent-bright">
                  {(s.implied_edge * 100).toFixed(1)}%
                </span>
              )}
            </Link>
          ))
        )}
      </RailSection>
    </aside>
  );
}
