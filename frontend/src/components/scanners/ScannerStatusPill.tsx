"use client";

import { cn } from "@/lib/cn";
import type { ScannerStatus } from "@/lib/scanners-api";

/*
 * Loop V84 (U2) — scanner status pill. Ticket color contract, positional:
 * draft/active/paused/failed → mint/blue/amber/gray. Danger-red is never
 * used for scanner state (no red anywhere in the studio).
 */

const PILL_STYLES: Record<ScannerStatus, string> = {
  draft: "border-primary/40 bg-primary/10 text-primary",
  active: "border-secondary/40 bg-secondary/10 text-secondary",
  paused: "border-gold/40 bg-gold/10 text-gold",
  failed: "border-border-light bg-surface-2 text-muted",
};

const DOT_STYLES: Record<ScannerStatus, string> = {
  draft: "bg-primary",
  active: "bg-secondary animate-pulse",
  paused: "bg-gold",
  failed: "bg-muted-2",
};

export function ScannerStatusPill({
  status,
  className,
}: {
  status: ScannerStatus;
  className?: string;
}) {
  return (
    <span
      data-testid="scanner-status-pill"
      data-status={status}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em]",
        PILL_STYLES[status],
        className,
      )}
    >
      <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", DOT_STYLES[status])} />
      {status}
    </span>
  );
}
