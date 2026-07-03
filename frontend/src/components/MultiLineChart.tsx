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
import { fetchLatestPrice, fetchMarketCandlesMeta } from "@/lib/alphaedge-api";
import { generateCandles, pct, type Market, type MarketOutcome, type OutcomeTone } from "@/lib/mock-data";
import { isLiveMirror } from "@/lib/hero-market";
import { resolveOutcomeSlug, wsBase } from "@/lib/live-price";
import { cn } from "@/lib/cn";
import { formatProbabilityAxis } from "@/lib/probability-format";

function sortMatchOutcomes(outcomes: MarketOutcome[]): MarketOutcome[] {
  return [...outcomes].sort((a, b) => {
    const aTie = /tie|draw/i.test(a.label);
    const bTie = /tie|draw/i.test(b.label);
    if (aTie && !bTie) return -1;
    if (bTie && !aTie) return 1;
    return b.price - a.price;
  });
}

const LINE: Record<OutcomeTone, string> = {
  primary: "#05b169",
  danger: "#e5484d",
  accent: "#0052ff",
  gold: "#FFB020",
  muted: "#a8acb3",
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
  candleSlug: string;
  api: ISeriesApi<"Line">;
  data: { time: UTCTimestamp; value: number }[];
};

function candleSlugForOutcome(outcome: MarketOutcome, marketSlug: string): string {
  return resolveOutcomeSlug(outcome.id, marketSlug);
}

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
  const liveYesRef = useRef<Record<string, number>>({});
  const hoveringRef = useRef(false);
  const [range, setRange] = useState<RangeKey>("1D");
  const [hovering, setHovering] = useState(false);
  const [liveConnected, setLiveConnected] = useState(false);
  const [candleMeta, setCandleMeta] = useState<{ source: string; points: number } | null>(
    null,
  );

  const outcomes = useMemo(
    () => sortMatchOutcomes(market.outcomes.slice(0, 4)),
    [market.outcomes],
  );
  const isLive = isLiveMirror(market);
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(outcomes.map((o) => [o.id, o.price])),
  );

  const cfg = useMemo(() => RANGES.find((r) => r.key === range) ?? RANGES[2], [range]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a8acb3",
        fontFamily: "var(--font-mono), monospace",
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "rgba(35,40,56,0.64)" },
      },
      rightPriceScale: {
        borderColor: "#26292f",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: { borderColor: "#26292f", timeVisible: true, secondsVisible: false },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { color: "#0052ff", width: 1, style: 2, labelBackgroundColor: "#0052ff" },
        horzLine: { visible: false, labelVisible: false },
      },
      autoSize: true,
    });
    chartRef.current = chart;

    linesRef.current = outcomes.map((o) => ({
      id: o.id,
      label: o.label,
      tone: o.tone,
      candleSlug: candleSlugForOutcome(o, market.slug),
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
        hoveringRef.current = false;
        setHovering(false);
        return;
      }
      const next: Record<string, number> = {};
      for (const line of linesRef.current) {
        const point = param.seriesData.get(line.api) as { value?: number } | undefined;
        if (typeof point?.value === "number") next[line.id] = point.value;
      }
      if (Object.keys(next).length) {
        hoveringRef.current = true;
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

  // Load candle history from API (live) or seed generator (mock).
  useEffect(() => {
    let cancelled = false;

    async function load() {
      let metaSource = "unknown";
      let metaPoints = 0;

      for (const line of linesRef.current) {
        const o = outcomes.find((x) => x.id === line.id);
        const end = o?.price ?? 0.5;
        let data: { time: UTCTimestamp; value: number }[];

        if (isLive) {
          const meta = await fetchMarketCandlesMeta(line.candleSlug, cfg.points);
          if (cancelled) return;
          const apiCandles = meta?.candles ?? [];
          metaSource = meta?.source ?? "live";
          metaPoints = Math.max(metaPoints, apiCandles.length);
          if (apiCandles.length > 0) {
            data = apiCandles.map((c) => ({
              time: c.time as UTCTimestamp,
              value: c.close,
            }));
          } else {
            const now = Math.floor(Date.now() / 1000) as UTCTimestamp;
            data = [{ time: now, value: end }];
            metaPoints = 1;
          }
        } else {
          const meta = await fetchMarketCandlesMeta(line.candleSlug, cfg.points);
          if (cancelled) return;
          const apiCandles = meta?.candles;
          data = (apiCandles && apiCandles.length > 0
            ? apiCandles
            : generateCandles(`${market.slug}:${line.label}`, cfg.points, end, cfg.stepSec)
          ).map((c) => ({ time: c.time as UTCTimestamp, value: c.close }));
        }

        line.data = data;
        line.api.setData(data);
      }
      if (!cancelled) {
        setCandleMeta({ source: metaSource, points: metaPoints });
      }
      chartRef.current?.timeScale().fitContent();
      setValues(Object.fromEntries(outcomes.map((o) => [o.id, o.price])));
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [market.slug, cfg, outcomes, isLive]);

  // Live Polymarket: HTTP poll + websocket (no fake random drift).
  useEffect(() => {
    if (!isLive) return;
    let dead = false;
    const slugs = [...new Set(linesRef.current.map((l) => l.candleSlug))];

    const applyLiveYes = (slug: string, yes: number) => {
      liveYesRef.current[slug] = yes;
      const next: Record<string, number> = {};
      const now = Math.floor(Date.now() / 1000) as UTCTimestamp;

      for (const line of linesRef.current) {
        const yesForLine = liveYesRef.current[line.candleSlug] ?? yes;
        const o = outcomes.find((x) => x.id === line.id);
        const isComplement =
          outcomes.length === 2 && o?.id === "no";
        const value = isComplement ? 1 - yesForLine : yesForLine;
        const last = line.data[line.data.length - 1];

        if (!last) {
          const point = { time: now, value };
          line.data.push(point);
          line.api.update(point);
          next[line.id] = value;
          continue;
        }

        if (Math.abs(last.value - value) < 0.0002 && now - last.time < 30) {
          next[line.id] = value;
          continue;
        }

        const point =
          last.time === now
            ? { time: now, value }
            : { time: now, value };
        if (last.time === now) {
          line.data[line.data.length - 1] = point;
        } else {
          line.data.push(point);
        }
        line.api.update(point);
        next[line.id] = value;
      }

      if (!hoveringRef.current && Object.keys(next).length) {
        setValues((prev) => ({ ...prev, ...next }));
        setCandleMeta((prev) =>
          prev ? { ...prev, points: Math.max(prev.points, 1) } : { source: "live", points: 1 },
        );
      }
    };

    const poll = async () => {
      for (const slug of slugs) {
        const latest = await fetchLatestPrice(slug);
        if (dead || !latest) continue;
        applyLiveYes(slug, latest.yes);
      }
    };

    void poll();
    const pollId = setInterval(() => void poll(), 2000);

    const sockets: WebSocket[] = [];

    for (const slug of slugs) {
      const ws = new WebSocket(`${wsBase()}/api/v1/ws/prices?market=${encodeURIComponent(slug)}`);
      sockets.push(ws);
      ws.onopen = () => setLiveConnected(true);
      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data) as { yes?: number; keepalive?: boolean };
          if (d.keepalive || typeof d.yes !== "number") return;
          applyLiveYes(slug, d.yes);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => setLiveConnected(false);
    }

    return () => {
      dead = true;
      clearInterval(pollId);
      for (const ws of sockets) ws.close();
    };
  }, [market.slug, isLive, outcomes]);

  // Mock markets only: subtle random drift for demo feel.
  useEffect(() => {
    if (isLive) return;
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
      if (!hovering) setValues((prev) => ({ ...prev, ...next }));
    }, 1600);
    return () => clearInterval(interval);
  }, [market.slug, hovering, isLive]);

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
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
          {isLive && (
            <span className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-wider text-[#05b169]">
              <span className="h-2 w-2 animate-pulse rounded-full bg-[#05b169]" />
              Live API
              {candleMeta ? (
                <span className="font-mono font-semibold normal-case text-white/40">
                  · {candleMeta.points} ticks ({candleMeta.source})
                </span>
              ) : null}
            </span>
          )}
        </div>

        <div className="flex rounded-xl border border-border bg-bg p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={cn(
                "rounded-lg px-2 py-1 text-[11px] font-semibold transition",
                range === r.key ? "bg-accent text-white" : "text-muted hover:text-text",
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
