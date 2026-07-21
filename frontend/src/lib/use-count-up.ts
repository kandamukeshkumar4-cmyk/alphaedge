"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Loop V79 (A8) — number counters animate from 0 with ease-out over 500ms on
 * first paint (later changes tween from the previous value). Reduced motion:
 * the value snaps instantly — no tween at all.
 */
export function useCountUp(target: number, durationMs = 500): number {
  const [value, setValue] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    if (!Number.isFinite(target)) return;
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      fromRef.current = target;
      setValue(target);
      return;
    }
    const from = fromRef.current;
    if (from === target) {
      setValue(target);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      setValue(Math.round(from + (target - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    fromRef.current = target;
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return value;
}
