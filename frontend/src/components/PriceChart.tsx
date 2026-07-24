"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  AreaSeries,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { fetchMarketCandles } from "@/lib/alphaedge-api";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import { generateCandles, cents, type Candle } from "@/lib/mock-data";
import { cn } from "@/lib/cn";
import { ChartAttribution } from "@/components/ChartAttribution";
import {
  observeChartTheme,
  readLwcChartTheme,
  type LwcChartTheme,
} from "@/lib/chart-colors";

// QuestFlow Trade terminal chips: 5m · 15m · 1h · 6h · 1d · 1w · 1m · All
type RangeKey = "5m" | "15m" | "1h" | "6h" | "1d" | "1w" | "1m" | "All";
const RANGES: { key: RangeKey; points: number; stepSec: number }[] = [
  { key: "5m", points: 60, stepSec: 5 },
  { key: "15m", points: 90, stepSec: 10 },
  { key: "1h", points: 60, stepSec: 60 },
  { key: "6h", points: 72, stepSec: 300 },
  { key: "1d", points: 96, stepSec: 900 },
  { key: "1w", points: 168, stepSec: 3600 },
  { key: "1m", points: 120, stepSec: 21600 },
  { key: "All", points: 180, stepSec: 14400 },
];

type Mode = "area" | "candle";

// Theme tokens: chart-colors resolves CSS vars off <html>; re-apply on .light.

function applyChartTheme(
  chart: IChartApi,
  area: ISeriesApi<"Area"> | null,
  candle: ISeriesApi<"Candlestick"> | null,
  vol: ISeriesApi<"Histogram"> | null,
  t: LwcChartTheme,
): void {
  chart.applyOptions({
    layout: { textColor: t.text },
    grid: { vertLines: { color: t.grid }, horzLines: { color: t.grid } },
    rightPriceScale: { borderColor: t.border },
    timeScale: { borderColor: t.border },
    crosshair: {
      vertLine: { color: t.accent, labelBackgroundColor: t.accent },
      horzLine: { color: t.accent, labelBackgroundColor: t.accent },
    },
  });
  area?.applyOptions({
    lineColor: t.accent,
    topColor: t.accentSoft,
    bottomColor: t.accentFade,
  });
  candle?.applyOptions({
    upColor: t.up,
    downColor: t.down,
    borderUpColor: t.up,
    borderDownColor: t.down,
    wickUpColor: t.up,
    wickDownColor: t.down,
  });
  vol?.applyOptions({ color: t.accentSoft });
}

export function PriceChart({
  slug,
  endPrice,
  modelProb,
  height = 360,
  compact = false,
  live = true,
}: {
  slug: string;
  endPrice: number;
  modelProb?: number;
  height?: number;
  compact?: boolean;
  live?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const areaRef = useRef<ISeriesApi<"Area"> | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const modelLineRef = useRef<ReturnType<ISeriesApi<"Area">["createPriceLine"]> | null>(null);
  const dataRef = useRef<Candle[]>([]);

  const isApiModeRef = useRef<boolean>(false);
  const [range, setRange] = useState<RangeKey>("1d");
  const [mode, setMode] = useState<Mode>("area");
  const [apiCandles, setApiCandles] = useState<Candle[] | null>(null);
  const [last, setLast] = useState(endPrice);
  const [hovered, setHovered] = useState<number | null>(null);
  const [openPrice, setOpenPrice] = useState(endPrice);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  const livePrice = useMarketPrice(slug, live);

  const cfg = useMemo(
    () => RANGES.find((r) => r.key === range) ?? RANGES[4],
    [range],
  );

  // Build / rebuild the chart instance once.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const theme = readLwcChartTheme();
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme.text,
        fontFamily: "var(--font-mono), monospace",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border, timeVisible: true, secondsVisible: false },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { color: theme.accent, width: 1, style: 2, labelBackgroundColor: theme.accent },
        horzLine: { color: theme.accent, width: 1, style: 2, labelBackgroundColor: theme.accent },
      },
      handleScale: { mouseWheel: true, pinch: true },
      handleScroll: true,
      autoSize: true,
    });
    chartRef.current = chart;

    const area = chart.addSeries(AreaSeries, {
      lineColor: theme.accent,
      topColor: theme.accentSoft,
      bottomColor: theme.accentFade,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });
    areaRef.current = area;

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: theme.up,
      downColor: theme.down,
      borderUpColor: theme.up,
      borderDownColor: theme.down,
      wickUpColor: theme.up,
      wickDownColor: theme.down,
      priceLineVisible: false,
      visible: false,
    });
    candleRef.current = candle;

    if (!compact) {
      const vol = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "vol",
        color: theme.accentSoft,
      });
      vol.priceScale().applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });
      volRef.current = vol;
    }

    chart.subscribeCrosshairMove((param) => {
      if (!param.point || param.time === undefined) {
        setHovered(null);
        return;
      }
      const v = param.seriesData.get(area) as { value?: number } | undefined;
      const c = param.seriesData.get(candle) as { close?: number } | undefined;
      const price = v?.value ?? c?.close;
      if (typeof price === "number") setHovered(price);
    });

    // Re-theme when the user flips the .light class on <html>.
    const observer = observeChartTheme(() => {
      applyChartTheme(
        chart,
        areaRef.current,
        candleRef.current,
        volRef.current,
        readLwcChartTheme(),
      );
    });

    return () => {
      observer?.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [compact]);

  useEffect(() => {
    let cancelled = false;
    fetchMarketCandles(slug, cfg.points).then((candles) => {
      if (!cancelled) {
        setApiCandles(candles);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [slug, cfg.points]);

  // Load data when range or API candles change.
  useEffect(() => {
    const candles =
      apiCandles ?? generateCandles(slug, cfg.points, endPrice, cfg.stepSec);
    isApiModeRef.current = apiCandles !== null;
    dataRef.current = candles;
    const areaData = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      value: c.close,
    }));
    const candleData = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    const volData = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      value: Math.abs(c.close - c.open) * 90000 + 2000,
      color: c.close >= c.open ? readLwcChartTheme().volUp : readLwcChartTheme().volDown,
    }));
    areaRef.current?.setData(areaData);
    candleRef.current?.setData(candleData);
    volRef.current?.setData(volData);
    chartRef.current?.timeScale().fitContent();
    setOpenPrice(candles[0]?.close ?? endPrice);
    setLast(candles[candles.length - 1]?.close ?? endPrice);
  }, [slug, cfg, endPrice, apiCandles]);

  // Toggle series visibility.
  useEffect(() => {
    areaRef.current?.applyOptions({ visible: mode === "area" });
    candleRef.current?.applyOptions({ visible: mode === "candle" });
  }, [mode]);

  // AI model read drawn as a dashed reference line (the "vs market" comparison).
  useEffect(() => {
    const area = areaRef.current;
    if (!area) return;
    if (modelLineRef.current) {
      area.removePriceLine(modelLineRef.current);
      modelLineRef.current = null;
    }
    if (typeof modelProb === "number") {
      modelLineRef.current = area.createPriceLine({
        price: modelProb,
        color: readLwcChartTheme().model,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "AI",
      });
    }
  }, [modelProb, range]);

  // Live ticks from WS hub when connected; fall back to no-op in seed mode.
  useEffect(() => {
    if (!livePrice.connected || livePrice.ts === null) return;
    const newClose = livePrice.yes;
    const data = dataRef.current;
    if (data.length === 0) return;
    const lastCandle = data[data.length - 1];
    const updated: Candle = {
      ...lastCandle,
      close: newClose,
      high: Math.max(lastCandle.high, newClose),
      low: Math.min(lastCandle.low, newClose),
    };
    data[data.length - 1] = updated;
    const t = updated.time as UTCTimestamp;
    areaRef.current?.update({ time: t, value: newClose });
    candleRef.current?.update({
      time: t,
      open: updated.open,
      high: updated.high,
      low: updated.low,
      close: newClose,
    });
    setFlash(newClose >= lastCandle.close ? "up" : "down");
    setLast(newClose);
    // M-REL-05: clear the flash timer on unmount / next tick so it can't fire
    // setFlash after the component is gone (React state-update-on-unmounted warn).
    const flashTimer = setTimeout(() => setFlash(null), 700);
    return () => clearTimeout(flashTimer);
  }, [livePrice.yes, livePrice.ts, livePrice.connected]);

  const shown = hovered ?? last;
  const change = shown - openPrice;
  const changePct = openPrice ? (change / openPrice) * 100 : 0;
  const up = change >= 0;

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-end justify-between gap-3 px-1">
        <div>
          <div className="flex items-baseline gap-3">
            <span
              className={cn(
                "rounded px-1 font-mono text-3xl font-black tabular sm:text-4xl",
                flash === "up" && "animate-flash-green",
                flash === "down" && "animate-flash-red",
              )}
            >
              {cents(shown)}
            </span>
            <span
              className={cn(
                "font-mono text-sm font-bold tabular",
                up ? "text-primary" : "text-danger",
              )}
            >
              {up ? "▲" : "▼"} {Math.abs(change * 100).toFixed(1)}¢ ({up ? "+" : ""}
              {changePct.toFixed(1)}%)
            </span>
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm bg-accent" />
              {hovered !== null ? "hovered" : live ? "Market · live" : "Market · snapshot"}
            </span>
            {typeof modelProb === "number" && (
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-secondary" />
                AI {cents(modelProb)}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-xl border border-border bg-surface p-0.5">
            {(["area", "candle"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                aria-pressed={mode === m}
                className={cn(
                  "rounded-lg px-2.5 py-1 text-xs font-semibold capitalize transition",
                  mode === m ? "bg-accent-bright text-bg" : "text-muted hover:text-text",
                )}
              >
                {m}
              </button>
            ))}
          </div>
          <div className="flex rounded-xl border border-border bg-surface p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.key}
                onClick={() => setRange(r.key)}
                aria-pressed={range === r.key}
                className={cn(
                  "rounded-lg px-2 py-1 text-xs font-semibold transition",
                  range === r.key ? "bg-accent-bright text-bg" : "text-muted hover:text-text",
                )}
              >
                {r.key}
              </button>
            ))}
          </div>
        </div>
      </div>
      {apiCandles === null ? (
        <p className="mt-3 text-center text-xs text-muted-2">
          Synthetic chart — generated from sample data, not live candles.
        </p>
      ) : null}

      <div
        ref={containerRef}
        className="mt-3 w-full"
        style={{ height }}
        role="img"
        aria-label={`Price history chart, currently ${cents(shown)}${
          typeof modelProb === "number" ? `, AI estimate ${cents(modelProb)}` : ""
        }`}
      />
      <ChartAttribution className="mt-1 px-1" />
    </div>
  );
}
