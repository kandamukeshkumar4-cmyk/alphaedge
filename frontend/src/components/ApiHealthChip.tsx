"use client";

import { useApiHealth } from "@/hooks/useApiHealth";
import { cn } from "@/lib/cn";

// Header LIVE/DEMO indicator (P03). Reads the shared `useApiHealth` probe and
// never presents demo fixtures as live: green pulse = backend reachable,
// amber = sample data / unreachable, neutral = first probe in flight.
const STYLES = {
  live: {
    label: "Live",
    dot: "bg-primary",
    chip: "border-primary/30 bg-primary/10 text-primary",
    pulse: true,
    title: "Backend reachable — surfaces show live data.",
  },
  demo: {
    label: "Demo",
    dot: "bg-gold",
    chip: "border-gold/30 bg-gold/10 text-gold",
    pulse: false,
    title:
      "Backend unreachable or unconfigured — live data unavailable. AlphaEdge will not invent markets or scores as live.",
  },
  checking: {
    label: "Checking",
    dot: "bg-muted",
    chip: "border-border bg-surface-2 text-muted",
    pulse: true,
    title: "Checking backend health…",
  },
} as const;

export function ApiHealthChip({ className }: { className?: string }) {
  const health = useApiHealth();
  const style = STYLES[health];

  return (
    <span
      role="status"
      aria-live="polite"
      title={style.title}
      className={cn(
        "inline-flex select-none items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.1em]",
        style.chip,
        className,
      )}
    >
      <span
        className={cn("h-1.5 w-1.5 rounded-full", style.dot, style.pulse && "animate-pulse")}
        aria-hidden
      />
      {style.label}
    </span>
  );
}
