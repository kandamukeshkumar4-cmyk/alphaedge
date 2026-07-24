"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import { chartRgb, observeChartTheme, readLwcChartTheme } from "@/lib/chart-colors";
import { type IndicatorPoint, sma } from "@/lib/indicators-api";

/*
 * Loop 99 AU3 — compact price + SMA-20 overlay chart for the TA panel.
 * Price area is brand mint; the rolling SMA-20 overlay is gold (blue is
 * reserved for down-states, red for trade direction — never used here).
 * The SMA series is derived client-side from the same points the backend
 * used, so the overlay stays honest to the displayed window.
 */

const SMA_WINDOW = 20;
const SMA_GOLD = () => chartRgb("--color-gold", "246, 194, 68");

function smaOverlay(points: IndicatorPoint[]): { time: UTCTimestamp; value: number }[] {
  const out: { time: UTCTimestamp; value: number }[] = [];
  for (let i = SMA_WINDOW - 1; i < points.length; i++) {
    const mean = sma(points.slice(i - SMA_WINDOW + 1, i + 1).map((p) => p.close), SMA_WINDOW);
    if (mean !== null) out.push({ time: points[i]!.t as UTCTimestamp, value: mean });
  }
  return out;
}

function applyTheme(
  chart: IChartApi,
  price: ISeriesApi<"Area"> | null,
  smaLine: ISeriesApi<"Line"> | null,
): void {
  const theme = readLwcChartTheme();
  chart.applyOptions({
    layout: { textColor: theme.text },
    grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border },
    crosshair: {
      vertLine: { color: theme.accent, labelBackgroundColor: theme.accent },
      horzLine: { color: theme.accent, labelBackgroundColor: theme.accent },
    },
  });
  price?.applyOptions({
    lineColor: theme.accent,
    topColor: theme.accentSoft,
    bottomColor: theme.accentFade,
  });
  smaLine?.applyOptions({ color: SMA_GOLD() });
}

export function IndicatorPriceChart({
  points,
  height = 240,
}: {
  points: IndicatorPoint[];
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || points.length < 2) return;

    const theme = readLwcChartTheme();
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme.text,
        fontFamily: "var(--font-mono), monospace",
        attributionLogo: false,
      },
      grid: { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
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

    const price = chart.addSeries(AreaSeries, {
      lineColor: theme.accent,
      topColor: theme.accentSoft,
      bottomColor: theme.accentFade,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      priceFormat: { type: "price", precision: 3, minMove: 0.001 },
    });

    const smaLine = chart.addSeries(LineSeries, {
      color: SMA_GOLD(),
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      priceFormat: { type: "price", precision: 3, minMove: 0.001 },
    });

    price.setData(
      points.map((p) => ({ time: p.t as UTCTimestamp, value: p.close })),
    );
    smaLine.setData(smaOverlay(points));
    chart.timeScale().fitContent();

    // Re-theme when the user flips the .light class on <html>.
    const observer = observeChartTheme(() => applyTheme(chart, price, smaLine));

    return () => {
      observer?.disconnect();
      chart.remove();
    };
  }, [points]);

  return (
    <div>
      <div
        ref={containerRef}
        data-testid="indicators-chart"
        role="img"
        aria-label={`YES close price over ${points.length} bars with a ${SMA_WINDOW}-bar simple moving average overlay`}
        className="w-full"
        style={{ height }}
      />
      <div className="mt-1.5 flex items-center gap-4 px-1 text-[11px] font-semibold text-muted-2">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-primary" />
          Close (YES)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 border-t-2 border-dashed border-gold" />
          SMA {SMA_WINDOW}
        </span>
      </div>
    </div>
  );
}
