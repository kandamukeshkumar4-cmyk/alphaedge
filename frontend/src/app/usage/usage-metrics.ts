/**
 * Loop V85 (D-U2, G2) — shared metric tokens for the /usage page.
 *
 * Astryx palette, one color per activity metric: mint / blue / amber / gray.
 * NEVER red — this page has no negative/down state, so danger red is
 * deliberately absent from every series, chip, and numeral.
 *
 * Array order is the canonical stacking + column order: sessions at the
 * bottom of the stack and first column, briefs on top / last.
 */

import type { UsageTotals } from "@/lib/usage-api";

export type UsageMetricKey = keyof UsageTotals;

export type UsageMetric = {
  key: UsageMetricKey;
  /** Card / legend label. */
  label: string;
  /** Table column header. */
  column: string;
  hex: string;
  /** Canvas-safe "R, G, B" triplet for lightweight-charts. */
  triplet: string;
};

export const USAGE_METRICS: UsageMetric[] = [
  {
    key: "sessions",
    label: "Sessions",
    column: "Sessions",
    hex: "#00E8B0",
    triplet: "0, 232, 176",
  },
  {
    key: "skill_runs",
    label: "Skill runs",
    column: "Skill runs",
    hex: "#4B9EFF",
    triplet: "75, 158, 255",
  },
  {
    key: "scanner_runs",
    label: "Scanner runs",
    column: "Scanner runs",
    hex: "#F6C244",
    triplet: "246, 194, 68",
  },
  {
    key: "briefs",
    label: "Briefs",
    column: "Briefs",
    hex: "#8FA8A0",
    triplet: "143, 168, 160",
  },
];

const DAY_FMT = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "2-digit",
  timeZone: "UTC",
});

/** `2026-07-21` → `Tue · Jul 21` (UTC — matches the backend's calendar days). */
export function formatUsageDate(iso: string): string {
  const t = Date.parse(`${iso}T00:00:00Z`);
  if (!Number.isFinite(t)) return iso;
  return DAY_FMT.format(new Date(t)).replace(",", " ·");
}
