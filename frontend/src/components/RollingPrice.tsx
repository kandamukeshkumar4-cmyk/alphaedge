"use client";

import { cn } from "@/lib/cn";
import { pct, type Market, type MarketOutcome } from "@/lib/mock-data";

export function formatKalshiCents(price: number): string {
  const cents = price * 100;
  if (cents < 0.05) return "<1¢";
  if (cents < 1) return `${cents.toFixed(1)}¢`;
  return `${Math.round(cents)}¢`;
}

/** Plain live price — updates when value changes, no animation effects. */
export function RollingPrice({
  value,
  cents = false,
  className,
}: {
  value: number | null;
  cents?: boolean;
  flash?: "up" | "down" | null;
  className?: string;
}) {
  const text =
    value != null && value > 0
      ? cents
        ? formatKalshiCents(value)
        : pct(value)
      : "—";
  return (
    <span className={cn("font-mono font-black tabular text-inherit", className)}>{text}</span>
  );
}
