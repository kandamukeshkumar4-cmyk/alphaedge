"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  LineSeries,
  ColorType,
  CrosshairMode,
  LineType,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { generateCandles, pct, type Market, type OutcomeTone } from "@/lib/mock-data";
import { cn } from "@/lib/cn";
import { formatProbabilityAxis } from "@/lib/probability-format";

const LINE: Record<OutcomeTone, string> = {
  primary: "#24C66D",
  danger: "#FF4D4F",
  accent: "#39B8FF",
  gold: "#FFB020",
  muted: "#9EA9A3",
};

const DOT: Record<OutcomeTone, string> = {
  primary: "bg-primary",
  danger: "bg-danger",
  accent: "bg-accent",
  gold: "bg-gold",
  muted: "bg-muted",
};

type RangeKey = "1H" | "6H" | "1D" | "1W" | "ALL";
const RANGES: { key: RangeKey; points: number; stepSec: number }[] = [
  { key: "1H", points: 60, stepSec: 60 },
  { key: "6H", points: 72, stepSec: 300 },
  { key: "1D", points: 96, stepSec: 900 },
  { key: "1W", points: 168, stepSec: 3600 },
  { key: "ALL", points: 180, stepSec: 14400 },
];

type Line = {
  id: string;
  label: string;
  tone: OutcomeTone;
  api: ISeriesApi<"Line">;
  data: { time: UTCTimestamp; value: number }[];
};

export function MultiLineChart({
  market,
  height = 300,
}: {
  market: Market;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const linesRef = useRef<Line[]>([]);
  const [range, setRange] = useState<RangeKey>("1D");
  const [hovering, setHovering] = useState(false);

  const outcomes = useMemo(() => market.outcomes.slice(0, 4), [market]);
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(outcomes.map((o) => [o.id, o.price])),
  );

  const cfg = useMemo(() => RANGES.find((r) => r.key === range) ?? RANGES[2], [range]);

  // Create chart + one line series per outcome (rebuilt when market changes).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9EA9A3",
        fontFamily: "var(--font-mono), monospace",
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "rgba(36,48,57,0.64)" },
      },
      rightPriceScale: {
        borderColor: "#243039",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: { borderColor: "#243039", timeVisible: true, secondsVisible: false },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { color: "#24C66D", width: 1, style: 2, labelBackgroundColor: "#24C66D" },
        horzLine: { visible: false, labelVisible: false },
      },
      autoSize: true,
    });
    chartRef.current = chart;

    linesRef.current = outcomes.map((o) => ({
      id: o.id,
      label: o.label,
      tone: o.tone,
      api: chart.addSeries(LineSeries, {
        color: LINE[o.tone],
        lineWidth: 2,
        lineType: LineType.WithSteps,
        priceLineVisible: false,
        lastValueVisible: true,
        priceFormat: {
          type: "custom",
          minMove: 0.01,
          formatter: formatProbabilityAxis,
          tickmarksFormatter: (prices: number[]) => prices.map(formatProbabilityAxis),
        },
      }),
      data: [],
    }));

    chart.subscribeCrosshairMove((param) => {
      if (!param.point || param.time === undefined) {
        setHovering(false);
        return;
      }
      const next: Record<string, number> = {};
      for (const line of linesRef.current) {
        const point = param.seriesData.get(line.api) as { value?: number } | undefined;
        if (typeof point?.value === "number") next[line.id] = point.value;
      }
      if (Object.keys(next).length) {
        setHovering(true);
        setValues((prev) => ({ ...prev, ...next }));
      }
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      linesRef.current = [];
    };
  }, [market.slug, outcomes]);

  // Load each line's data when the range changes.
  useEffect(() => {
    for (const line of linesRef.current) {
      const o = outcomes.find((x) => x.id === line.id);
      const end = o?.price ?? 0.5;
      const data = generateCandles(
        `${market.slug}:${line.label}`,
        cfg.points,
        end,
        cfg.stepSec,
      ).map((c) => ({ time: c.time as UTCTimestamp, value: c.close }));
      line.data = data;
      line.api.setData(data);
    }
    chartRef.current?.timeScale().fitContent();
    setValues(Object.fromEntries(outcomes.map((o) => [o.id, o.price])));
  }, [market.slug, cfg, outcomes]);

  // Live ticks: nudge each line's last point.
  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const interval = setInterval(() => {
      const next: Record<string, number> = {};
      for (const line of linesRef.current) {
        const last = line.data[line.data.length - 1];
        if (!last) continue;
        const drift = (Math.random() - 0.5) * 0.015;
        const value = Math.min(0.97, Math.max(0.03, last.value + drift));
        const updated = { time: last.time, value };
        line.data[line.data.length - 1] = updated;
        line.api.update(updated);
        next[line.id] = value;
      }
      // Only update the legend live when the user isn't scrubbing.
      setValues((prev) => (hovering ? prev : { ...prev, ...next }));
    }, 1600);
    return () => clearInterval(interval);
  }, [market.slug, hovering]);

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        {/* Legend (Kalshi-style) */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {outcomes.map((o) => (
            <span key={o.id} className="flex items-center gap-1.5 text-sm">
              <span className={cn("h-2.5 w-2.5 rounded-full", DOT[o.tone])} />
              <span className="text-muted">{o.label}</span>
              <span className="font-mono font-bold text-text tabular">
                {pct(values[o.id] ?? o.price)}
              </span>
            </span>
          ))}
        </div>

        {/* Range tabs */}
        <div className="flex rounded-md border border-border bg-bg p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={cn(
                "rounded px-2 py-1 text-[11px] font-semibold transition",
                range === r.key ? "bg-surface-3 text-text" : "text-muted hover:text-text",
              )}
            >
              {r.key}
            </button>
          ))}
        </div>
      </div>

      <div ref={containerRef} className="mt-3 w-full" style={{ height }} />
    </div>
  );
}
