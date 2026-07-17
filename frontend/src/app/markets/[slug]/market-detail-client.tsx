"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getMarket,
  type Market,
  pct,
  multiplier,
  formatCompactUSD,
  toneClass,
} from "@/lib/mock-data";
import { PriceChart } from "@/components/PriceChartLazy";
import { OrderBook } from "@/components/OrderBook";
import { AIForecastPanel } from "@/components/AIForecastPanel";
import { LockedForecastPanel } from "@/components/LockedForecastPanel";
import { MarketTabs } from "@/components/MarketTabs";
import { DecisionSignalPanel } from "@/components/DecisionSignalPanel";
import { DecisionCard } from "@/components/DecisionCard";
import { ResolutionBanner } from "@/components/ResolutionBanner";
import { PredictionWidget } from "@/components/PredictionWidget";
import { MarketTradingPanel } from "@/components/MarketTradingPanel";
import { LatencyBadge } from "@/components/LatencyBadge";
import { WatchlistStar } from "@/components/WatchlistStar";
import { OrderbookDepthChart } from "@/components/OrderbookDepthChart";
import { ProbabilityHistoryChart } from "@/components/ProbabilityHistoryChartLazy";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import { cn } from "@/lib/cn";
import {
  fetchMarketDetail,
  fetchMarketDetailApi,
  type MarketDetailApi,
} from "@/lib/alphaedge-api";
import { SimilarMarkets } from "@/components/SimilarMarkets";
import { SimilarPastMarkets } from "@/components/SimilarPastMarkets";
import { QuestMarketRail } from "@/components/quest/QuestMarketRail";
import { DeskIntelligencePanel } from "@/components/DeskIntelligencePanel";
import { MarketContextPanel } from "@/components/MarketContextPanel";
import { useAtlasPanel } from "@/context/atlas-panel";
import {
  marketCloseCountdown,
  marketLifecycleFromDetail,
} from "@/lib/market-lifecycle";

const PROVISIONAL_LABEL = "⚠️ Provisional — model not yet CLV-validated";
const PAPER_DISCLAIMER =
  "This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only.";

export default function MarketDetailClient({
  slug,
  initialDetail = null,
}: {
  slug: string;
  initialDetail?: MarketDetailApi | null;
}) {
  const { openPanel } = useAtlasPanel();
  const [apiMarket, setApiMarket] = useState<Market | null>(null);
  const [apiDetail, setApiDetail] = useState<MarketDetailApi | null>(initialDetail);
  const [loadedApi, setLoadedApi] = useState(false);
  const localMarket = getMarket(slug);
  const market = apiMarket ?? localMarket;
  const forecastProvisional = apiDetail?.forecast?.provisional ?? true;
  const resolutionOutcome = apiDetail?.resolution_outcome ?? null;
  const resolutionCriteria =
    apiDetail?.resolution_criteria ?? market?.resolution ?? "Resolution criteria unavailable.";

  useEffect(() => {
    let cancelled = false;
    // Live catalog slugs (pm-/ks-) exist only on the API; a single transient
    // failure (HF Space 429 / cold start) must not drop the page to the mock
    // catalog. Retry once with backoff and keep whatever live fields loaded.
    const isLiveSlug = slug.startsWith("pm-") || slug.startsWith("ks-");

    const load = async (attempt: number): Promise<void> => {
      const [detail, nextMarket] = await Promise.all([
        fetchMarketDetailApi(slug),
        fetchMarketDetail(slug),
      ]);
      if (cancelled) return;
      if (detail) setApiDetail(detail);
      if (nextMarket) setApiMarket(nextMarket);
      if (!detail && !nextMarket && isLiveSlug && attempt < 2) {
        setTimeout(() => {
          if (!cancelled) void load(attempt + 1);
        }, 2_000 * (attempt + 1));
        return;
      }
      setLoadedApi(true);
    };

    void load(0);
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const lifecycle = market
    ? marketLifecycleFromDetail(market, apiDetail, apiMarket?.endsAt)
    : null;
  const isResolved = Boolean(apiDetail?.resolved) || lifecycle === "decided";
  const livePrice = useMarketPrice(slug, lifecycle === "live" && !isResolved);

  if (!market && loadedApi) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-20 text-center">
        <h1 className="text-2xl font-black">Market not found</h1>
        <Link href="/" className="mt-4 inline-block text-accent hover:underline">
          ← Back to markets
        </Link>
      </main>
    );
  }

  if (!market) {
    return (
      <main className="mx-auto max-w-[1400px] px-4 py-6">
        <div className="skeleton h-72 w-full" />
      </main>
    );
  }

  const displayOutcome =
    apiDetail?.winning_outcome ?? apiDetail?.resolution_outcome ?? resolutionOutcome;
  const closeCountdown = marketCloseCountdown(lifecycle, market.endsAt);

  return (
    <main className="theme-polymarket mx-auto max-w-[1400px] overflow-x-hidden px-4 py-6">
      <ResolutionBanner
        outcome={isResolved ? displayOutcome : null}
        resolvedAt={apiDetail?.resolved_at}
      />

      {/* Breadcrumb + title */}
      <div className="flex items-center gap-2 text-xs text-muted">
        <Link href="/" className="hover:text-text">
          Markets
        </Link>
        <span>/</span>
        <span>{market.category}</span>
      </div>

        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface-2 text-2xl">
            {market.icon}
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-black text-text sm:text-2xl">
                {apiDetail?.title ?? market.title}
              </h1>
              {lifecycle === "live" && !isResolved ? <LatencyBadge slug={market.slug} /> : null}
            </div>
            <p className="mt-0.5 text-sm text-muted">
              {market.question === "Paper market snapshot unavailable"
                ? apiDetail?.title ?? market.title
                : market.question}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
          <WatchlistStar slug={market.slug} />
          <button
            type="button"
            onClick={() =>
              openPanel({
                mode: "analyze",
                marketSlug: market.slug,
                marketTitle: market.title,
                seedPrompt: `Deep-dive ${market.title}. Current YES ~${Math.round((livePrice.connected && livePrice.yes > 0 ? livePrice.yes : market.outcomes[0]?.price ?? 0.5) * 100)}¢.`,
              })
            }
            className="rounded-lg border border-primary/40 bg-primary-dim px-3 py-2 text-sm font-bold text-primary shadow-glow transition hover:bg-primary hover:text-bg"
          >
            ✦ AI Analyze
          </button>
          <Link
            href={`/trade?slug=${encodeURIComponent(market.slug)}`}
            className="rounded-lg border border-border px-3 py-2 text-sm font-bold text-muted transition hover:text-text"
          >
            Trade view
          </Link>
          {isResolved ? (
            <span className="rounded-md bg-primary-dim px-2 py-1 font-bold uppercase text-primary">
              Decided {resolutionOutcome ?? ""}
            </span>
          ) : lifecycle === "live" && livePrice.connected ? (
            <span className="flex items-center gap-1 text-xs font-medium text-green-400">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-green-400" />
              LIVE
            </span>
          ) : lifecycle === "closed" ? (
            <span className="rounded-md bg-surface-3 px-2 py-1 font-bold text-muted">
              Closed
            </span>
          ) : null}
          <span className="font-mono">{formatCompactUSD(market.volume)} vol</span>
          {/* Traders/closes come from the mock catalog for unknown slugs; a
              live pm-/ks- market must omit them rather than show fake stats. */}
          {apiMarket && market.traders > 0 ? (
            <span className="font-mono">{market.traders.toLocaleString()} traders</span>
          ) : null}
          {closeCountdown ? (
            <span className="rounded-md bg-surface-2 px-2 py-1 font-mono">
              closes {closeCountdown}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left: chart, outcomes, book, AI, tabs */}
        <div className="min-w-0 space-y-5">
          {(() => {
            const yes =
              livePrice.connected && livePrice.yes > 0
                ? livePrice.yes
                : market.outcomes[0]?.price ?? 0.5;
            const chance = Math.round(yes * 100);
            const deltaPts = Math.round((yes - (market.forecast?.prob ?? yes)) * 100);
            return (
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-3xl font-black tabular-nums text-text sm:text-4xl">
                  {chance}.0%
                </span>
                <span className="text-lg font-semibold text-muted">Chance</span>
                <span className="text-sm text-muted-2">— {market.outcomes[0]?.label ?? "YES"}</span>
                {deltaPts !== 0 && (
                  <span
                    className={cn(
                      "font-mono text-sm font-semibold tabular-nums",
                      deltaPts >= 0 ? "text-primary" : "text-danger",
                    )}
                  >
                    {deltaPts >= 0 ? "↗ +" : "↘ "}
                    {Math.abs(deltaPts)} pts
                  </span>
                )}
              </div>
            );
          })()}
          <div className="rounded-2xl border border-border bg-surface p-4">
            <PriceChart
              slug={market.slug}
              live={lifecycle === "live" && !isResolved}
              endPrice={
                livePrice.connected && livePrice.yes > 0
                  ? livePrice.yes
                  : market.outcomes[0].price
              }
              modelProb={apiDetail?.forecast?.model_prob ?? market.forecast.prob}
              height={360}
            />
          </div>

          {/* Outcome strip */}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {market.outcomes.map((o) => {
              const displayPrice =
                livePrice.connected && o.label === "YES"
                  ? livePrice.yes
                  : livePrice.connected && o.label === "NO"
                    ? livePrice.no
                    : o.price;

              return (
                <div
                  key={o.id}
                  className="flex items-center justify-between rounded-xl border border-border bg-surface px-3 py-2.5"
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-text">
                    <span>{o.emoji}</span>
                    {o.label}
                  </span>
                  <span className="flex items-baseline gap-2">
                    <span className="font-mono text-[11px] text-muted-2">
                      {multiplier(displayPrice)}
                    </span>
                    <span className={cn("font-mono text-lg font-black", toneClass(o.tone))}>
                      {pct(displayPrice)}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>

          <ProbabilityHistoryChart slug={slug} height={100} />

          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-3">
              <OrderbookDepthChart slug={slug} />
              <OrderBook market={market} />
            </div>
            <div className="space-y-3">
              {forecastProvisional ? (
                <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200">
                  {PROVISIONAL_LABEL}
                </p>
              ) : null}
              <LockedForecastPanel slug={slug} />
              <AIForecastPanel market={market} />
              <SimilarPastMarkets category={market.category} currentSlug={slug} />
            </div>
          </div>

          <section className="rounded-2xl border border-border bg-surface p-4">
            <h2 className="text-sm font-bold uppercase tracking-wide text-muted">
              Resolution criteria
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-text">{resolutionCriteria}</p>
          </section>

          <MarketTabs market={market} />
        </div>

        {/* Right: sticky trade panel */}
        <div className="flex flex-col gap-5 lg:sticky lg:top-28 lg:self-start">
          <PredictionWidget slug={slug} className="mt-4" />
          {/* D01: one desk call replaces the per-market signal-events fetch
              (QuestMarketActivity) and adds edge/smart-money/arb in situ. */}
          <DeskIntelligencePanel slug={slug} />
          {/* Loop V60 (U4): master context snapshot — descriptive telemetry
              only (whale pressure / venue gap / news tone); honest states
              until the context endpoint ships. */}
          <MarketContextPanel slug={slug} />
          <QuestMarketRail slug={slug} />
          <DecisionSignalPanel market={market} />
          <DecisionCard slug={slug} />
          <button
            type="button"
            onClick={() =>
              openPanel({
                mode: "chat",
                marketSlug: slug,
                marketTitle: market.title,
                seedPrompt: `Why did odds move on ${market.title}?`,
              })
            }
            className="rounded-2xl border border-accent/30 bg-accent-dim/40 px-4 py-3 text-left transition hover:border-primary/50"
          >
            <p className="text-xs font-bold uppercase tracking-wider text-primary">ATLAS</p>
            <p className="mt-1 text-sm text-muted">
              Analysis only — open the AI rail for briefs. Cannot place trades.
            </p>
          </button>
          <MarketTradingPanel
            slug={slug}
            title={market.title}
            status={
              isResolved || resolutionOutcome != null
                ? "resolved"
                : lifecycle === "closed"
                  ? "closed"
                  : "open"
            }
            closeTime={market.endsAt}
            initialYesPrice={
              livePrice.connected && livePrice.yes > 0
                ? livePrice.yes
                : market.outcomes[0]?.price ?? 0.5
            }
          />
        </div>
      </div>

      <div className="mt-6">
        <SimilarMarkets currentSlug={slug} category={market.category} />
      </div>

      <footer className="mt-8 rounded-2xl border border-border bg-surface-2 px-4 py-3 text-center text-xs text-muted">
        {PAPER_DISCLAIMER}
      </footer>
    </main>
  );
}
