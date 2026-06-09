"use client";

import { useEffect, useRef, useState } from "react";

import { useMarketPrice } from "@/hooks/useMarketPrice";
import { cn } from "@/lib/cn";

type FlashDirection = "up" | "down" | null;

function usePriceFlash(value: number, loading: boolean): FlashDirection {
  const prev = useRef(value);
  const [flash, setFlash] = useState<FlashDirection>(null);

  useEffect(() => {
    if (loading || value === prev.current) {
      return;
    }
    setFlash(value > prev.current ? "up" : "down");
    prev.current = value;
    const timer = window.setTimeout(() => setFlash(null), 400);
    return () => window.clearTimeout(timer);
  }, [value, loading]);

  return flash;
}

export function LivePriceDisplay({ slug }: { slug: string }) {
  const { yes, no, connected } = useMarketPrice(slug);
  const loading = !connected;
  const yesFlash = usePriceFlash(yes, loading);
  const noFlash = usePriceFlash(no, loading);

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm font-semibold">
      <span
        className={cn(
          "transition-colors duration-300",
          yesFlash === "up" && "text-up",
          yesFlash === "down" && "text-down",
        )}
      >
        YES {loading ? "—" : `${(yes * 100).toFixed(1)}%`}
      </span>
      <span className="text-muted">/</span>
      <span
        className={cn(
          "transition-colors duration-300",
          noFlash === "up" && "text-up",
          noFlash === "down" && "text-down",
        )}
      >
        NO {loading ? "—" : `${(no * 100).toFixed(1)}%`}
      </span>
    </div>
  );
}
