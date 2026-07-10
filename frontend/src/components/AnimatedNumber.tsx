"use client";

// F06: animated number transition for prices/edges/counts. Tweens the displayed
// value with an ease-out and respects prefers-reduced-motion (jumps instantly).
import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

/** Ease-out cubic — fast then settling. Pure, exported for testing. */
export function easeOutCubic(t: number): number {
  const c = Math.max(0, Math.min(1, t));
  return 1 - Math.pow(1 - c, 3);
}

export function AnimatedNumber({
  value,
  format,
  durationMs = 600,
  className,
}: {
  value: number;
  format: (n: number) => string;
  durationMs?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduced || durationMs <= 0) {
      fromRef.current = value;
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const to = value;
    if (from === to) return;
    const start =
      typeof performance !== "undefined" ? performance.now() : Date.now();

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      setDisplay(from + (to - from) * easeOutCubic(t));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [value, reduced, durationMs]);

  return <span className={className}>{format(reduced ? value : display)}</span>;
}
