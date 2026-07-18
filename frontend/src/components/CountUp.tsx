"use client";

import { useEffect, useRef, useState } from "react";

import { easeOutCubic } from "@/components/AnimatedNumber";

/*
 * Loop V62 (R4) — count-up ticker for stat reveals. Animates 0 → value once the
 * element scrolls into view (IntersectionObserver), then holds. Respects
 * prefers-reduced-motion by rendering the final value with no tween.
 *
 * Reduced-motion is read once via matchMedia (the same signal the globals.css
 * kill-switch uses) and is deliberately NOT an effect dependency — framer's
 * useReducedMotion settles null->false after mount, which would re-run the
 * effect and cancel an in-flight count. Safe to drop into a server component
 * as a client island (e.g. the /features total).
 *
 * Loop V71: when `value` changes, clear the one-shot `started` latch so the
 * display re-animates (or jumps immediately under reduced-motion / durationMs≤0).
 */

/** Clear the one-shot latch so a new target value can animate (or setDisplay). */
export function resetCountUpStarted(started: { current: boolean }): void {
  started.current = false;
}

export function CountUp({
  value,
  durationMs = 900,
  format = (n) => String(Math.round(n)),
  className,
}: {
  value: number;
  durationMs?: number;
  format?: (n: number) => string;
  className?: string;
}) {
  // Start at 0 on server + first client render (matches SSR to avoid a
  // hydration mismatch); the effect fills in the real value.
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    // Value (or duration) changed — allow run() again; otherwise a prior
    // animation leaves started=true and the display never updates.
    resetCountUpStarted(started);

    const reduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduced || durationMs <= 0) {
      setDisplay(value);
      return;
    }

    const node = ref.current;
    let raf = 0;
    let settle = 0;
    const run = () => {
      if (started.current) return;
      started.current = true;
      const start =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / durationMs);
        setDisplay(value * easeOutCubic(t));
        if (t < 1) raf = requestAnimationFrame(tick);
        else setDisplay(value);
      };
      raf = requestAnimationFrame(tick);
      // Guarantee the true value lands even if rAF is throttled (background
      // tab, reduced perf). A stat must never be left showing a wrong number.
      settle = window.setTimeout(() => setDisplay(value), durationMs + 120);
    };

    const inViewport = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      return r.top < window.innerHeight && r.bottom > 0;
    };

    // Already visible (e.g. an above-the-fold stat) — count immediately and
    // don't depend on an IntersectionObserver callback firing.
    if (!node || typeof IntersectionObserver === "undefined" || inViewport(node)) {
      run();
      return () => {
        if (raf) cancelAnimationFrame(raf);
        if (settle) window.clearTimeout(settle);
      };
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          run();
          observer.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(node);
    // Fallback: never leave the number stuck at 0 if the observer is throttled
    // or never fires — count anyway after a short delay.
    const fallback = window.setTimeout(run, 1200);
    return () => {
      observer.disconnect();
      window.clearTimeout(fallback);
      if (raf) cancelAnimationFrame(raf);
      if (settle) window.clearTimeout(settle);
    };
  }, [value, durationMs]);

  return (
    <span ref={ref} className={className}>
      {format(display)}
    </span>
  );
}
