"use client";

import { useEffect, useState } from "react";
import { fetchOrderBook, type OrderBookResponse } from "@/lib/alphaedge-api";
import { CHART_COLOR_FALLBACKS, chartRgba } from "@/lib/chart-colors";

const W = 480;
const H = 80;
const PAD = { t: 6, r: 8, b: 18, l: 40 };
const INNER_W = W - PAD.l - PAD.r;
const INNER_H = H - PAD.t - PAD.b;

type DepthBar = { price: number; cumSize: number; side: "bid" | "ask" };

function buildDepth(book: OrderBookResponse): DepthBar[] {
  const yes = book.yes;
  const bids: DepthBar[] = [];
  let cum = 0;
  for (const lvl of [...(yes.bids ?? [])].sort((a, b) => b.price - a.price)) {
    cum += lvl.size;
    bids.push({ price: lvl.price, cumSize: cum, side: "bid" });
  }
  const asks: DepthBar[] = [];
  cum = 0;
  for (const lvl of [...(yes.asks ?? [])].sort((a, b) => a.price - b.price)) {
    cum += lvl.size;
    asks.push({ price: lvl.price, cumSize: cum, side: "ask" });
  }
  return [...bids.reverse(), ...asks];
}

export function OrderbookDepthChart({ slug }: { slug: string }) {
  const [bars, setBars] = useState<DepthBar[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchOrderBook(slug).then((book) => {
      if (!cancelled && book) {
        setBars(buildDepth(book));
      }
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [slug]);

  if (loading) {
    return (
      <div className="h-20 animate-pulse rounded-xl bg-surface-2" />
    );
  }

  if (bars.length === 0) {
    return (
      <div className="flex h-20 items-center justify-center rounded-xl border border-border bg-surface text-xs text-muted-2">
        No order book data
      </div>
    );
  }

  const prices = bars.map((b) => b.price);
  const sizes = bars.map((b) => b.cumSize);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const maxS = Math.max(...sizes);
  const pRange = maxP - minP || 0.01;

  function px(price: number) {
    return PAD.l + ((price - minP) / pRange) * INNER_W;
  }
  function py(size: number) {
    return PAD.t + INNER_H - (size / maxS) * INNER_H;
  }

  const bidBars = bars.filter((b) => b.side === "bid");
  const askBars = bars.filter((b) => b.side === "ask");

  function barWidth() {
    if (bars.length < 2) return 8;
    return Math.max(3, (INNER_W / bars.length) * 0.8);
  }
  const bw = barWidth();

  const bidFill = chartRgba("--color-primary", CHART_COLOR_FALLBACKS.primary, 0.35);
  const askFill = chartRgba("--color-danger", CHART_COLOR_FALLBACKS.danger, 0.35);

  return (
    <div className="rounded-xl border border-border bg-surface p-2">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-2">
        Depth · YES
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        aria-label="Order book depth chart"
      >
        {/* Bid bars */}
        {bidBars.map((b) => {
          const x = px(b.price);
          const y = py(b.cumSize);
          return (
            <rect
              key={`bid-${b.price}`}
              x={x - bw / 2}
              y={y}
              width={bw}
              height={INNER_H - (y - PAD.t)}
              fill={bidFill}
              rx={2}
            />
          );
        })}

        {/* Ask bars */}
        {askBars.map((b) => {
          const x = px(b.price);
          const y = py(b.cumSize);
          return (
            <rect
              key={`ask-${b.price}`}
              x={x - bw / 2}
              y={y}
              width={bw}
              height={INNER_H - (y - PAD.t)}
              fill={askFill}
              rx={2}
            />
          );
        })}

        {/* Price axis labels */}
        {[minP, (minP + maxP) / 2, maxP].map((p) => (
          <text
            key={p}
            x={px(p)}
            y={H - 3}
            textAnchor="middle"
            fontSize={8}
            fill="currentColor"
            className="text-muted-2"
            opacity={0.6}
          >
            {(p * 100).toFixed(0)}¢
          </text>
        ))}

        {/* Midpoint line */}
        {bidBars.length > 0 && askBars.length > 0 && (
          <line
            x1={px((bidBars[bidBars.length - 1]!.price + askBars[0]!.price) / 2)}
            x2={px((bidBars[bidBars.length - 1]!.price + askBars[0]!.price) / 2)}
            y1={PAD.t}
            y2={PAD.t + INNER_H}
            stroke="currentColor"
            strokeWidth={1}
            strokeDasharray="3 2"
            opacity={0.3}
          />
        )}
      </svg>
    </div>
  );
}
