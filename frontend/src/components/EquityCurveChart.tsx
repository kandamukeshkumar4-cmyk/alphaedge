"use client";

/**
 * U10 — EquityCurveChart using lightweight-charts (same pattern as PriceChart.tsx).
 * Renders the equity curve from a backtest replay.
 * Honest: if equity_curve is empty, renders the honest empty state — never fabricates.
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
import { type EquityPoint } from "@/lib/alphaedge-api";
import { ChartAttribution } from "@/components/ChartAttribution";
import {
  CHART_COLOR_FALLBACKS,
  chartRgb,
  observeChartTheme,
  readLwcChartTheme,
} from "@/lib/chart-colors";

interface EquityCurveChartProps {
  equityCurve: EquityPoint[];
  initialEquity: number;
  height?: number;
}

export function EquityCurveChart({
  equityCurve,
  initialEquity,
  height = 260,
}: EquityCurveChartProps) {
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
      timeScale: { borderVisible: false, timeVisible: true },
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
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || equityCurve.length === 0) return;
    const data = equityCurve.map((p) => ({
      time: (Math.floor(new Date(p.timestamp).getTime() / 1000)) as UTCTimestamp,
      value: p.equity,
    }));
    // Sort ascending by time (required by lightweight-charts)
    data.sort((a, b) => (a.time as number) - (b.time as number));
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [equityCurve]);

  if (equityCurve.length === 0) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center rounded-xl border border-border bg-surface text-sm text-muted-2"
      >
        No equity data — insufficient snapshots in range or no trades triggered
      </div>
    );
  }

  const finalEq = equityCurve[equityCurve.length - 1]?.equity ?? initialEquity;
  const pnl = finalEq - initialEquity;
  const pnlPct = ((pnl / initialEquity) * 100).toFixed(2);
  const isPositive = pnl >= 0;

  return (
    <div>
      <div className="mb-2 flex items-baseline gap-3">
        <span className="font-mono text-lg font-bold text-text">
          ${finalEq.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </span>
        <span
          className={
            isPositive ? "font-mono text-sm font-semibold text-primary" : "font-mono text-sm font-semibold text-danger"
          }
        >
          {isPositive ? "+" : ""}
          {pnlPct}%
        </span>
        <span className="text-xs text-muted-2">
          vs ${initialEquity.toLocaleString()} start
        </span>
      </div>
      {/* D04: canvas chart — expose an accessible summary for AT users. */}
      <div
        ref={containerRef}
        role="img"
        aria-label={`Equity curve: from $${initialEquity.toLocaleString()} to $${finalEq.toLocaleString(undefined, { maximumFractionDigits: 0 })} (${isPositive ? "+" : ""}${pnlPct}%) over ${equityCurve.length} points`}
      />
      <ChartAttribution className="mt-1" />
    </div>
  );
}
