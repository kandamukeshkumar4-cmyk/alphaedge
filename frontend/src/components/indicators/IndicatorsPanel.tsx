"use client";

import { useEffect, useState } from "react";

import { IndicatorPriceChart } from "@/components/indicators/IndicatorPriceChart";
import { cn } from "@/lib/cn";
import {
  fetchMarketIndicators,
  INDICATORS_DEFAULT_WINDOW,
  regimeLabel,
  type MarketIndicators,
  type ApiSource,
  type Regime,
} from "@/lib/indicators-api";

/*
 * Loop 99 AU3 — technical-analysis panel for the market detail page.
 *
 * Renders RSI / MACD / SMA / EMA / Bollinger / ADX from
 * GET /api/v1/markets/{slug}/indicators?window=90 plus a regime chip and a
 * compact close + SMA-20 chart. Down-states are BLUE (`secondary`), never
 * red — red stays reserved for trade direction. Paper-only: the backend
 * refuses this endpoint unless PAPER_TRADING_ONLY, and the panel says so.
 */

const REGIME_STYLE: Record<Regime, string> = {
  trending_up: "border-primary/40 bg-primary/10 text-primary",
  // Down is blue, not red.
  trending_down: "border-secondary/40 bg-secondary/10 text-secondary",
  range: "border-border-light bg-surface-2 text-muted",
  insufficient_data: "border-border bg-surface-2 text-muted-2",
};

function cents(value: number): string {
  return `${(value * 100).toFixed(1)}¢`;
}

function num(value: number | null, digits = 2): string {
  return value === null ? "—" : value.toFixed(digits);
}

type TileTone = "plain" | "mint" | "blue";

const TONE: Record<TileTone, string> = {
  plain: "text-text",
  mint: "text-primary",
  blue: "text-secondary",
};

function Tile({
  label,
  value,
  sub,
  tone = "plain",
  testId,
}: {
  label: string;
  value: string;
  sub: string;
  tone?: TileTone;
  testId: string;
}) {
  return (
    <div
      data-testid={testId}
      className="rounded-xl border border-border bg-surface-2/60 px-3 py-2.5 transition-colors duration-150 hover:border-border-light"
    >
      <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-2">{label}</p>
      <p className={cn("mt-1 font-mono text-lg font-black tabular-nums", TONE[tone])}>{value}</p>
      <p className="mt-0.5 text-[10px] font-medium leading-snug text-muted-2">{sub}</p>
    </div>
  );
}

export function IndicatorsPanel({ slug }: { slug: string }) {
  const [data, setData] = useState<MarketIndicators | null>(null);
  const [source, setSource] = useState<ApiSource | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetchMarketIndicators(slug, { window: INDICATORS_DEFAULT_WINDOW }).then(
      (result) => {
        if (cancelled) return;
        setData(result.data);
        setSource(result.source);
        setLoaded(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const indicators = data?.indicators ?? null;
  const hasAny =
    indicators !== null &&
    (indicators.rsi_14 !== null ||
      indicators.sma_20 !== null ||
      indicators.adx_14 !== null ||
      indicators.macd.macd !== null);
  const showEmpty = loaded && (!data || data.points.length < 20 || !hasAny);

  const last = data?.points[data.points.length - 1]?.close ?? null;
  const first = data?.points[0]?.close ?? null;
  const windowDelta = last !== null && first !== null ? last - first : null;

  const rsi = indicators?.rsi_14 ?? null;
  const rsiZone =
    rsi === null ? "needs 15+ bars" : rsi >= 70 ? "overbought ≥70" : rsi <= 30 ? "oversold ≤30" : "neutral band 30–70";
  const hist = indicators?.macd.hist ?? null;
  const sma20 = indicators?.sma_20 ?? null;
  const sma50 = indicators?.sma_50 ?? null;
  const smaTone: TileTone = sma20 === null || sma50 === null ? "plain" : sma20 > sma50 ? "mint" : "blue";
  const smaRel =
    sma20 === null || sma50 === null
      ? "needs 50+ bars"
      : sma20 > sma50
        ? "above SMA 50"
        : sma20 < sma50
          ? "below SMA 50" // blue, not red
          : "flat vs SMA 50";
  const adx = indicators?.adx_14 ?? null;

  return (
    <section
      data-testid="indicators-panel"
      className="rounded-2xl border border-border bg-surface p-4"
      aria-label="Technical indicators"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-black tracking-tight text-text">Technical analysis</h2>
          {data ? (
            <span
              data-testid="indicators-regime-chip"
              data-regime={data.regime}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] font-black tracking-[0.1em]",
                REGIME_STYLE[data.regime],
              )}
            >
              {data.regime === "trending_up" && <span aria-hidden>↗</span>}
              {data.regime === "trending_down" && <span aria-hidden>↘</span>}
              {data.regime === "range" && <span aria-hidden>↔</span>}
              {regimeLabel(data.regime).toUpperCase()}
            </span>
          ) : (
            <span className="skeleton h-5 w-24 rounded-full" />
          )}
        </div>
        <div className="flex items-center gap-2 font-mono text-[10px] font-bold tracking-[0.1em] text-muted-2">
          {windowDelta !== null && (
            <span
              className={cn(
                "tabular-nums",
                windowDelta >= 0 ? "text-primary" : "text-secondary",
              )}
              data-testid="indicators-window-delta"
            >
              {windowDelta >= 0 ? "+" : "−"}
              {Math.abs(windowDelta * 100).toFixed(1)}¢ / {INDICATORS_DEFAULT_WINDOW} bars
            </span>
          )}
          <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5">
            {source === "live" ? "LIVE" : "PAPER MOCK"} · W{INDICATORS_DEFAULT_WINDOW}
          </span>
        </div>
      </div>

      {showEmpty ? (
        <div
          data-testid="indicators-empty"
          className="mt-3 flex h-[240px] items-center justify-center rounded-xl border border-border bg-surface-2/40 px-4 text-center text-[12px] font-medium text-muted"
        >
          Not enough price bars for technical analysis on this market yet —
          indicators appear once the backend holds 20+ captured bars.
        </div>
      ) : !loaded || !data || !indicators ? (
        <div className="mt-3" data-testid="indicators-skeleton">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="skeleton h-[76px] rounded-xl" />
            ))}
          </div>
          <div className="skeleton mt-3 h-[240px] w-full rounded-xl" />
        </div>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            <Tile
              testId="indicators-tile-rsi"
              label="RSI 14"
              value={num(rsi, 1)}
              sub={rsiZone}
              tone={rsi !== null && (rsi >= 70 || rsi <= 30) ? "blue" : "plain"}
            />
            <Tile
              testId="indicators-tile-macd"
              label="MACD hist"
              value={num(hist, 4)}
              sub={`macd ${num(indicators.macd.macd, 4)} · sig ${num(indicators.macd.signal, 4)}`}
              tone={hist === null ? "plain" : hist >= 0 ? "mint" : "blue"}
            />
            <Tile
              testId="indicators-tile-sma20"
              label="SMA 20"
              value={sma20 === null ? "—" : cents(sma20)}
              sub={smaRel}
              tone={smaTone}
            />
            <Tile
              testId="indicators-tile-ema12"
              label="EMA 12"
              value={indicators.ema_12 === null ? "—" : cents(indicators.ema_12)}
              sub="fast trend filter"
            />
            <Tile
              testId="indicators-tile-bollinger"
              label="Bollinger"
              value={indicators.bollinger.mid === null ? "—" : cents(indicators.bollinger.mid)}
              sub={
                indicators.bollinger.lower === null || indicators.bollinger.upper === null
                  ? "needs 20+ bars"
                  : `${cents(indicators.bollinger.lower)} – ${cents(indicators.bollinger.upper)} · 2σ`
              }
            />
            <Tile
              testId="indicators-tile-adx"
              label="ADX 14"
              value={num(adx, 1)}
              sub={adx === null ? "needs 29+ bars" : adx > 20 ? "trending (>20)" : "no trend (≤20)"}
            />
          </div>
          <div className="mt-3">
            <IndicatorPriceChart points={data.points} height={240} />
          </div>
        </>
      )}

      <p className="mt-2.5 font-mono text-[10px] leading-relaxed text-muted-2">
        TA on outcome-price closes · descriptive research only · PAPER_TRADING_ONLY — no order path
      </p>
    </section>
  );
}
