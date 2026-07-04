"use client";

import { useEffect, useState } from "react";
import { cents, type Market, type BookLevel } from "@/lib/mock-data";

// Live-ish order book: sizes jitter on an interval to feel like a real feed.
export function OrderBook({ market }: { market: Market }) {
  const [bids, setBids] = useState<BookLevel[]>(market.bids);
  const [asks, setAsks] = useState<BookLevel[]>(market.asks);

  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const interval = setInterval(() => {
      const jitter = (lvl: BookLevel): BookLevel => ({
        price: lvl.price,
        size: Math.max(80, Math.round(lvl.size * (0.9 + Math.random() * 0.2))),
      });
      setBids((prev) => prev.map(jitter));
      setAsks((prev) => prev.map(jitter));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const maxSize = Math.max(
    ...bids.map((b) => b.size),
    ...asks.map((a) => a.size),
    1,
  );

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <h3 className="text-sm font-black text-text">Order book</h3>
      <div className="mt-3 grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 flex justify-between text-[11px] font-semibold uppercase tracking-wider text-muted-2">
            <span>Bid (Yes)</span>
            <span>Size</span>
          </div>
          <div className="space-y-0.5">
            {bids.slice(0, 7).map((lvl) => (
              <Level key={`b-${lvl.price}`} lvl={lvl} maxSize={maxSize} tone="bid" />
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1 flex justify-between text-[11px] font-semibold uppercase tracking-wider text-muted-2">
            <span>Ask (No)</span>
            <span>Size</span>
          </div>
          <div className="space-y-0.5">
            {asks.slice(0, 7).map((lvl) => (
              <Level key={`a-${lvl.price}`} lvl={lvl} maxSize={maxSize} tone="ask" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Level({
  lvl,
  maxSize,
  tone,
}: {
  lvl: BookLevel;
  maxSize: number;
  tone: "bid" | "ask";
}) {
  const w = `${(lvl.size / maxSize) * 100}%`;
  return (
    <div className="relative flex items-center justify-between overflow-hidden rounded px-2 py-1 font-mono text-xs">
      <span
        className="absolute inset-y-0 right-0"
        style={{
          width: w,
          background:
            tone === "bid" ? "rgba(47,107,255,0.14)" : "rgba(241,88,92,0.14)",
        }}
      />
      <span className={tone === "bid" ? "relative text-primary" : "relative text-danger"}>
        {cents(lvl.price)}
      </span>
      <span className="relative tabular text-muted">{lvl.size.toLocaleString()}</span>
    </div>
  );
}
