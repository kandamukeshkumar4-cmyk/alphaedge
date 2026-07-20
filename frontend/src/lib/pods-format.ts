import { relativeTime } from "@/lib/alerts-api";

/** Last-decision label: em-dash when missing or unparseable. */
export function formatLastDecisionAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  return relativeTime(iso) || "—";
}
