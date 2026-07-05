"use client";

import { useEffect, useRef, useState } from "react";
import { fetchMarketCandles } from "@/lib/alphaedge-api";
import { generateCandles } from "@/lib/mock-data";
import { useLivePrice } from "@/context/live-prices";

const MAX_POINTS = 48;

export function useLiveSparkline(
  slug: string,
  fallbackPrice: number,
  source?: string,
): { data: number[]; up: boolean; flash: "up" | "down" | null } {
  const live = useLivePrice(slug, fallbackPrice);
  const isLive = source === "polymarket" || source === "kalshi";
  const [data, setData] = useState<number[]>([]);
  const seeded = useRef(false);

  useEffect(() => {
    seeded.current = false;
    if (!isLive) {
      setData(generateCandles(slug, 36, fallbackPrice, 900).map((c) => c.close));
      return;
    }

    let dead = false;
    void fetchMarketCandles(slug, 36).then((candles) => {
      if (dead) return;
      if (candles?.length) {
        setData(candles.map((c) => c.close));
        seeded.current = true;
      } else {
        setData(generateCandles(slug, 36, fallbackPrice, 900).map((c) => c.close));
      }
    });
    return () => {
      dead = true;
    };
  }, [slug, fallbackPrice, isLive]);

  useEffect(() => {
    if (!isLive || live.price <= 0) return;
    setData((prev) => {
      const base = prev.length ? prev : [fallbackPrice];
      const last = base[base.length - 1];
      if (last === live.price) return base;
      return [...base, live.price].slice(-MAX_POINTS);
    });
  }, [live.price, isLive, fallbackPrice]);

  const series = data.length >= 2 ? data : [fallbackPrice, live.price || fallbackPrice];
  const up = series[series.length - 1] >= series[0];

  return { data: series, up, flash: isLive ? live.flash : null };
}
