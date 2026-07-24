"use client";

/**
 * V92 PU2 — paper equity curve from portfolio analytics pnl_series.
 * lightweight-charts mint line; reserved height; never fabricates points.
 * Losses are informational (blue elsewhere on the surface) — the curve itself
 * is always mint per UI-DIRECTION chart rule.
 */

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import { ChartAttribution } from "@/components/ChartAttribution";
import {
  CHART_COLOR_FALLBACKS,
  chartRgb,
  observeChartTheme,
  readLwcChartTheme,
} from "@/lib/chart-colors";
import type { PnLSeriesPoint } from "@/lib/portfolio-analytics-api";

const CHART_HEIGHT = 220;

export function AnalyticsEquityChart({
  series,
  height = CHART_HEIGHT,
}: {
  series: PnLSeriesPoint[];
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

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
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: false },
      crosshair: { horzLine: { visible: true }, vertLine: { visible: true } },
    });

    seriesRef.current = chartRef.current.addSeries(LineSeries, {
      color: chartRgb("--color-primary", CHART_COLOR_FALLBACKS.primary),
      lineWidth: 2,
      priceLineVisible: false,
    });

    const obs = new ResizeObserver(() => {
      if (chartRef.current && el) {
        chartRef.current.applyOptions({ width: el.clientWidth });
      }
    });
    obs.observe(el);

    const themeObserver = observeChartTheme(() => {
      const next = readLwcChartTheme();
      chartRef.current?.applyOptions({
        layout: { textColor: next.text },
        grid: {
          vertLines: { color: next.grid },
          horzLines: { color: next.grid },
        },
      });
      seriesRef.current?.applyOptions({
        color: chartRgb("--color-primary", CHART_COLOR_FALLBACKS.primary),
      });
    });

    return () => {
      themeObserver?.disconnect();
      obs.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || series.length === 0) return;
    const data = series
      .map((p) => {
        const ms = Date.parse(`${p.date}T00:00:00Z`);
        if (!Number.isFinite(ms)) return null;
        return {
          time: Math.floor(ms / 1000) as UTCTimestamp,
          value: p.equity,
        };
      })
      .filter((p): p is { time: UTCTimestamp; value: number } => p !== null)
      .sort((a, b) => (a.time as number) - (b.time as number));
    if (data.length === 0) return;
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [series]);

  if (series.length === 0) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center rounded-xl border border-border bg-surface-2/40 text-sm text-muted"
        data-testid="analytics-equity-empty"
      >
        No equity trail in this window — paper trades will draw the curve here.
      </div>
    );
  }

  const last = series[series.length - 1]!;
  const first = series[0]!;
  const delta = last.equity - first.equity;

  return (
    <div data-testid="analytics-equity-chart">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-lg font-bold text-text">
          {formatPaperUsd(last.equity)}
        </span>
        <span
          className={
            delta >= 0
              ? "font-mono text-sm font-semibold text-primary"
              : "font-mono text-sm font-semibold text-secondary"
          }
        >
          {formatSignedPaperUsd(delta)}
        </span>
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-2">
          paper equity
        </span>
      </div>
      <div
        ref={containerRef}
        style={{ height }}
        role="img"
        aria-label={`Paper equity curve from ${formatPaperUsd(first.equity)} to ${formatPaperUsd(last.equity)} over ${series.length} days`}
      />
      <ChartAttribution className="mt-1" />
    </div>
  );
}

function formatPaperUsd(value: number): string {
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedPaperUsd(value: number): string {
  const abs = formatPaperUsd(Math.abs(value));
  if (value > 0) return `+${abs}`;
  if (value < 0) return `−${abs}`;
  return abs;
}
