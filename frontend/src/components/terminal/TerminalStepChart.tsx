"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  AreaSeries,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import { ChartAttribution } from "@/components/ChartAttribution";
import { observeChartTheme, readLwcChartTheme } from "@/lib/chart-colors";
import type { ChartPayload } from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

export function TerminalStepChart({
  payload,
  className,
}: {
  payload: ChartPayload;
  className?: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const theme = readLwcChartTheme();
    const chart = createChart(host, {
      width: host.clientWidth || 640,
      height: 220,
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
        horzLine: { color: theme.accent, labelBackgroundColor: theme.accent },
      },
    });
    chartRef.current = chart;

    const series = chart.addSeries(AreaSeries, {
      lineColor: theme.accent,
      topColor: theme.accentSoft,
      bottomColor: theme.accentFade,
      lineWidth: 2,
    });
    seriesRef.current = series;

    const data = payload.points
      .filter((p) => Number.isFinite(p.t) && Number.isFinite(p.v))
      .map((p) => ({ time: p.t as UTCTimestamp, value: p.v }));
    series.setData(data);
    chart.timeScale().fitContent();

    const resize = new ResizeObserver(() => {
      if (chartRef.current && host) {
        chartRef.current.applyOptions({ width: host.clientWidth });
      }
    });
    resize.observe(host);

    const observer = observeChartTheme(() => {
      const next = readLwcChartTheme();
      chart.applyOptions({
        layout: { textColor: next.text },
        grid: { vertLines: { color: next.grid }, horzLines: { color: next.grid } },
        rightPriceScale: { borderColor: next.border },
        timeScale: { borderColor: next.border },
      });
      series.applyOptions({
        lineColor: next.accent,
        topColor: next.accentSoft,
        bottomColor: next.accentFade,
      });
    });

    return () => {
      resize.disconnect();
      observer?.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [payload]);

  return (
    <div className={cn("space-y-2", className)}>
      {payload.series_name ? (
        <p className="font-mono text-[11px] font-semibold uppercase tracking-wide text-muted">
          {payload.series_name}
          {payload.paper_pnl ? (
            <span className="ml-2 rounded border border-primary/30 bg-primary-dim/55 px-1.5 py-0.5 text-[9px] text-primary">
              PAPER ONLY
            </span>
          ) : null}
        </p>
      ) : null}
      <div
        ref={hostRef}
        data-testid="terminal-step-chart"
        className="h-[220px] w-full rounded-lg border border-border bg-bg/55"
      />
      <ChartAttribution />
    </div>
  );
}
