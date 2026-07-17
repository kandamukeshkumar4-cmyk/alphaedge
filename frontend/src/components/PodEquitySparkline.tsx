"use client";

/**
 * Loop V60 (U2) — compact equity sparkline for a pod card.
 * Same lightweight-charts pattern as EquityCurveChart/PriceChart, stripped to
 * chromeless card size. Line is tinted by the equity direction over the
 * window (up = primary token, down = danger token). Renders an honest empty
 * state when the curve has fewer than two points — never fabricates data.
 */

import { useEffect, useRef } from "react";
import {
  createChart,
  LineSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { PodEquityPoint } from "@/lib/pods-api";
import {
  CHART_COLOR_FALLBACKS,
  chartRgb,
  observeChartTheme,
  readLwcChartTheme,
} from "@/lib/chart-colors";

export function PodEquitySparkline({
  points,
  height = 56,
  podName,
}: {
  points: PodEquityPoint[];
  height?: number;
  podName: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const up = points.length >= 2 && points[points.length - 1]!.equity >= points[0]!.equity;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const theme = readLwcChartTheme();
    chartRef.current = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: { visible: false },
      leftPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: { horzLine: { visible: false }, vertLine: { visible: false } },
      handleScroll: false,
      handleScale: false,
    });

    seriesRef.current = chartRef.current.addSeries(LineSeries, {
      color: chartRgb(
        up ? "--color-primary" : "--color-danger",
        up ? CHART_COLOR_FALLBACKS.primary : CHART_COLOR_FALLBACKS.danger,
      ),
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const obs = new ResizeObserver(() => {
      if (chartRef.current && el) {
        chartRef.current.applyOptions({ width: el.clientWidth });
      }
    });
    obs.observe(el);

    const themeObserver = observeChartTheme(() => {
      seriesRef.current?.applyOptions({
        color: chartRgb(
          up ? "--color-primary" : "--color-danger",
          up ? CHART_COLOR_FALLBACKS.primary : CHART_COLOR_FALLBACKS.danger,
        ),
      });
    });

    return () => {
      themeObserver?.disconnect();
      obs.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height, up]);

  useEffect(() => {
    if (!seriesRef.current || points.length < 2) return;
    const data = points.map((p) => ({
      time: Math.floor(new Date(p.t).getTime() / 1000) as UTCTimestamp,
      value: p.equity,
    }));
    // lightweight-charts requires ascending unique timestamps.
    data.sort((a, b) => (a.time as number) - (b.time as number));
    const deduped = data.filter(
      (point, index) => index === 0 || point.time !== data[index - 1]!.time,
    );
    seriesRef.current.setData(deduped);
    chartRef.current?.timeScale().fitContent();
  }, [points]);

  if (points.length < 2) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center rounded-lg border border-border/60 bg-surface-2/40 text-[11px] text-muted-2"
      >
        No equity curve reported yet
      </div>
    );
  }

  const first = points[0]!.equity;
  const last = points[points.length - 1]!.equity;

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={`${podName} equity sparkline: ${up ? "up" : "down"} from $${first.toLocaleString(undefined, { maximumFractionDigits: 0 })} to $${last.toLocaleString(undefined, { maximumFractionDigits: 0 })} over ${points.length} points`}
    />
  );
}
