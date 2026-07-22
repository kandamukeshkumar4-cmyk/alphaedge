"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

import { ChartAttribution } from "@/components/ChartAttribution";
import { observeChartTheme, readLwcChartTheme } from "@/lib/chart-colors";
import type { UsageDay, UsageTotals } from "@/lib/usage-api";

import { USAGE_METRICS } from "./usage-metrics";

type StackedPoint = { time: Time; value: number };

type StackedSeries = {
  label: string;
  /** Canvas-safe rgb() string from the metric palette (never red). */
  color: string;
  points: StackedPoint[];
};

/**
 * lightweight-charts has no native stacking, so each of the four histogram
 * series carries the cumulative sum up to and including its metric, and the
 * series are added top-down (tallest cumulative first). Later, shorter
 * series overdraw the bottom of earlier ones, leaving one clean column
 * segment per metric: sessions mint at the bottom, then skill runs blue,
 * scanner runs amber, briefs gray on top. (HistogramSeries is LWC's filled-
 * column series; BarSeries is OHLC tick bars and wants open/high/low/close.)
 */
function buildStackedSeries(days: UsageDay[]): StackedSeries[] {
  const out: StackedSeries[] = [];
  for (let top = USAGE_METRICS.length - 1; top >= 0; top -= 1) {
    const metric = USAGE_METRICS[top]!;
    out.push({
      label: metric.label,
      color: `rgb(${metric.triplet})`,
      points: days.map((d) => {
        let cumulative = 0;
        for (let m = 0; m <= top; m += 1) cumulative += d[USAGE_METRICS[m]!.key];
        return { time: d.date as Time, value: cumulative };
      }),
    });
  }
  return out;
}

/**
 * Loop V85 (D-U2, G2) — stacked daily-activity bars. Reserved 280px height
 * (no CLS), canvas chrome follows the app theme, metric colors are fixed
 * palette constants. The crosshair's horizontal label is suppressed because
 * the stacked series carry cumulative values, not per-metric ones.
 */
export function UsageActivityChart({
  days,
  totals,
}: {
  days: UsageDay[];
  totals: UsageTotals;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<ISeriesApi<"Histogram">[]>([]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const theme = readLwcChartTheme();
    const chart = createChart(host, {
      width: host.clientWidth || 640,
      height: 280,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: theme.accent, labelBackgroundColor: theme.accent },
        horzLine: { labelVisible: false },
      },
    });
    chartRef.current = chart;

    const series = buildStackedSeries(days).map((s) => {
      // Single `color` per histogram — the palette has no red state.
      const column = chart.addSeries(HistogramSeries, {
        color: s.color,
        base: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: "volume" },
      });
      column.setData(s.points);
      return column;
    });
    seriesRefs.current = series;
    chart.timeScale().fitContent();

    const resize = new ResizeObserver(() => {
      if (chartRef.current && host) {
        chartRef.current.applyOptions({ width: host.clientWidth });
      }
    });
    resize.observe(host);

    // Metric colors are fixed palette constants; only the canvas chrome
    // re-themes (matches the other LWC surfaces in the app).
    const observer = observeChartTheme(() => {
      const next = readLwcChartTheme();
      chart.applyOptions({
        layout: { textColor: next.text },
        grid: { vertLines: { color: next.grid }, horzLines: { color: next.grid } },
        rightPriceScale: { borderColor: next.border },
        timeScale: { borderColor: next.border },
        crosshair: {
          vertLine: { color: next.accent, labelBackgroundColor: next.accent },
        },
      });
    });

    return () => {
      resize.disconnect();
      observer?.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRefs.current = [];
    };
  }, [days]);

  return (
    <div className="space-y-2">
      <div
        data-testid="usage-chart-legend"
        className="flex flex-wrap items-center gap-x-4 gap-y-1.5"
      >
        {USAGE_METRICS.map((m) => (
          <span
            key={m.key}
            className="flex items-center gap-1.5 font-mono text-[11px] text-muted"
          >
            <span
              aria-hidden
              className="h-2 w-2 rounded-[3px]"
              style={{ backgroundColor: m.hex }}
            />
            {m.label}
            <span className="tabular-nums text-text">{totals[m.key]}</span>
          </span>
        ))}
      </div>
      <div
        ref={hostRef}
        role="img"
        aria-label="Stacked bar chart of daily paper research activity over the last 14 days"
        data-testid="usage-chart"
        className="h-[280px] w-full rounded-lg border border-border bg-bg/55"
      />
      <ChartAttribution />
    </div>
  );
}
