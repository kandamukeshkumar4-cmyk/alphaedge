"use client";

/**
 * ConcentrationWarning — chip shown when one underlier dominates the book.
 * U04: displays per-underlier concentration alerts.
 */

import { cn } from "@/lib/cn";

type Props = {
  underlier: string;
  pctOfTotal: number;
  positionCount: number;
  netDirectional: number;
  className?: string;
};

export function ConcentrationWarning({
  underlier,
  pctOfTotal,
  positionCount,
  netDirectional,
  className,
}: Props) {
  const direction = netDirectional >= 0 ? "long" : "short";
  const directionLabel = netDirectional >= 0 ? "YES" : "NO";

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border border-secondary/40 bg-secondary/10 px-3 py-2 text-sm",
        className,
      )}
      role="alert"
    >
      <span className="mt-0.5 text-base leading-none text-secondary" aria-hidden>
        ⚠
      </span>
      <p className="text-text">
        You are effectively{" "}
        <strong className="font-bold text-secondary">
          {Math.round(pctOfTotal)}% {direction} {underlier}
        </strong>{" "}
        across {positionCount} market{positionCount !== 1 ? "s" : ""} (net{" "}
        {directionLabel}).
      </p>
    </div>
  );
}
