import { relativeTime } from "@/lib/alerts-api";

/**
 * Loop V60/V71 — /pods display helpers. Lives outside page.tsx because Next
 * app-router pages allow only canonical exports (loop71), while the loop71
 * tests need to import this directly.
 */

/** Last-decision label: em-dash when missing or unparseable. */
export function formatLastDecisionAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  return relativeTime(iso) || "—";
}
