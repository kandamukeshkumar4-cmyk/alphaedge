"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getMarket,
  type Market,
  pct,
  multiplier,
  formatCompactUSD,
  timeUntil,
  toneClass,
} from "@/lib/mock-data";
import { PriceChart } from "@/components/PriceChart";
import { TradePanel } from "@/components/TradePanel";
import { OrderBook } from "@/components/OrderBook";
import { AIForecastPanel } from "@/components/AIForecastPanel";
import { MarketTabs } from "@/components/MarketTabs";
import { DecisionSignalPanel } from "@/components/DecisionSignalPanel";
import MarketExplainer from "@/components/MarketExplainer";
import { PredictionWidget } from "@/components/PredictionWidget";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import { cn } from "@/lib/cn";
import {
  fetchMarketDetail,
  fetchMarketDetailApi,
  type MarketDetailApi,
} from "@/lib/alphaedge-api";
import { SimilarMarkets } from "@/components/SimilarMarkets";

const PROVISIONAL_LABEL = "⚠️ Provisional — model not yet CLV-validated";
const PAPER_DISCLAIMER =
  "This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only.";

export default function MarketDetailClient({ slug }: { slug: string }) {
  const [apiMarket, setApiMarket] = useState<Market | null>(null);
  const [apiDetail, setApiDetail] = useState<MarketDetailApi | null>(null);
  const [loadedApi, setLoadedApi] = useState(false);
  const localMarket = getMarket(slug);
  const market = apiMarket ?? localMarket;
  const forecastProvisional = apiDetail?.forecast?.provisional ?? true;
  const isResolved = apiDetail?.resolved ?? false;
  const resolutionOutcome = apiDetail?.resolution_outcome ?? null;
  const resolutionCriteria =
    apiDetail?.resolution_criteria ?? market?.resolution ?? "Resolution criteria unavailable.";

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMarketDetailApi(slug), fetchMarketDetail(slug)]).then(
      ([detail, nextMarket]) => {
        if (!cancelled) {
          setApiDetail(detail);
          setApiMarket(nextMarket);
          setLoadedApi(true);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const livePrice = useMarketPrice(slug);

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

  const resolvedBanner =
    resolutionOutcome != null
      ? `Market resolved — ${resolutionOutcome.toUpperCase()} wins`
      : null;

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      {resolvedBanner ? (
        <div
          className={cn(
            "mb-5 rounded-2xl border px-4 py-3 text-center text-sm font-bold",
            resolutionOutcome?.toUpperCase() === "YES"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              : "border-red-500/40 bg-red-500/10 text-red-200",
          )}
        >
          {resolvedBanner}
        </div>
      ) : null}

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
            <h1 className="text-xl font-black text-text sm:text-2xl">{market.title}</h1>
            <p className="mt-0.5 text-sm text-muted">{market.question}</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted">
          {isResolved ? (
            <span className="rounded-md bg-primary-dim px-2 py-1 font-bold uppercase text-primary">
              Resolved {resolutionOutcome ?? ""}
            </span>
          ) : null}
          {livePrice.connected && (
            <span className="flex items-center gap-1 text-xs font-medium text-green-400">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-green-400" />
              LIVE
            </span>
          )}
          <span className="font-mono">{formatCompactUSD(market.volume)} vol</span>
          <span className="font-mono">{market.traders.toLocaleString()} traders</span>
          <span className="rounded-md bg-surface-2 px-2 py-1 font-mono">
            closes {timeUntil(market.endsAt)}
          </span>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Left: chart, outcomes, book, AI, tabs */}
        <div className="min-w-0 space-y-5">
          <div className="rounded-2xl border border-border bg-surface p-4">
            <PriceChart
              slug={market.slug}
              endPrice={
                livePrice.connected && livePrice.yes > 0
                  ? livePrice.yes
                  : market.outcomes[0].price
              }
              modelProb={market.forecast.prob}
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

          <div className="grid gap-5 md:grid-cols-2">
            <OrderBook market={market} />
            <div className="space-y-3">
              {forecastProvisional ? (
                <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200">
                  {PROVISIONAL_LABEL}
                </p>
              ) : null}
              <AIForecastPanel market={market} />
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
          <DecisionSignalPanel market={market} />
          <MarketExplainer slug={slug} />
          {isResolved || resolutionOutcome != null ? (
            <div className="rounded-2xl border border-border bg-surface-2 px-4 py-6 text-center">
              <p className="text-sm font-bold uppercase tracking-[0.08em] text-muted">
                Trading closed
              </p>
              <p className="mt-2 text-base font-semibold text-text">
                This market is closed
              </p>
            </div>
          ) : (
            <TradePanel market={market} disabled={false} />
          )}
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
