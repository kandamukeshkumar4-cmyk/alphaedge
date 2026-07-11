"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  AreaSeries,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { fetchMarketHistory, type HistoryPoint } from "@/lib/alphaedge-api";

function directionArrow(history: HistoryPoint[]) {
  if (history.length < 2) return null;
  const first = history[0]!.yes_price;
  const last = history[history.length - 1]!.yes_price;
  const delta = last - first;
  return { delta, up: delta >= 0 };
}

export function ProbabilityHistoryChart({
  slug,
  height = 100,
}: {
  slug: string;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchMarketHistory(slug, 7).then((data) => {
      if (!cancelled) {
        setHistory(data);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [slug]);

  useEffect(() => {
    if (!containerRef.current || loading || history.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(160,160,180,0.7)",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.1, bottom: 0.1 },
        ticksVisible: true,
      },
      timeScale: { borderVisible: false, visible: true },
      handleScroll: false,
      handleScale: false,
      width: containerRef.current.clientWidth,
      height,
    });

    const isUp = (history[history.length - 1]?.yes_price ?? 0.5) >= (history[0]?.yes_price ?? 0.5);
    const color = isUp ? "rgb(var(--color-primary))" : "rgb(var(--color-danger))";

    const series = chart.addSeries(AreaSeries, {
      lineColor: color,
      topColor: color.replace("rgb(", "rgba(").replace(")", " / 0.25)"),
      bottomColor: color.replace("rgb(", "rgba(").replace(")", " / 0.01)"),
      lineWidth: 2,
      priceFormat: { type: "percent", precision: 0, minMove: 0.01 },
    });

    const points = history
      .filter((p) => p.yes_price > 0)
      .map((p) => ({
        time: p.timestamp as UTCTimestamp,
        value: p.yes_price * 100,
      }));
    series.setData(points);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) chart.applyOptions({ width: w });
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [history, loading, height]);

  const arrow = directionArrow(history);
  const lastPrice = history.length > 0 ? history[history.length - 1]!.yes_price : null;

  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-2">
          7-Day Probability
        </p>
        {lastPrice != null && arrow && (
          <div className="flex items-center gap-1.5">
            <span
              className={
                arrow.up
                  ? "font-mono text-sm font-bold text-primary"
                  : "font-mono text-sm font-bold text-danger"
              }
            >
              {(lastPrice * 100).toFixed(1)}%
            </span>
            <span className={arrow.up ? "text-primary" : "text-danger"}>
              {arrow.up ? "↑" : "↓"}
            </span>
          </div>
        )}
      </div>

      {loading ? (
        <div
          className="animate-pulse rounded bg-surface-2"
          style={{ height }}
        />
      ) : (
        <div
          ref={containerRef}
          role="img"
          aria-label={
            lastPrice != null
              ? `Probability history chart, currently ${(lastPrice * 100).toFixed(1)} percent`
              : "Probability history chart"
          }
        />
      )}
    </div>
  );
}
