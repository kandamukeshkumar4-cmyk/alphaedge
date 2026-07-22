import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  computeUsageTotals,
  getUsageSummary,
  setUsageFetch,
  USAGE_DEFAULT_DAYS,
  type UsageDay,
  type UsageTotals,
} from "@/lib/usage-api";

const TOTAL_KEYS: Array<keyof UsageTotals> = [
  "sessions",
  "skill_runs",
  "scanner_runs",
  "briefs",
];
/** Same four numeric fields as seen on a day row (excludes `date`). */
const DAY_KEYS: Array<keyof UsageDay> = TOTAL_KEYS;

function expectTotalsMatchDays(totals: UsageTotals, days: UsageDay[]): void {
  const sums = computeUsageTotals(days);
  for (const k of TOTAL_KEYS) expect(totals[k]).toBe(sums[k]);
}

describe("usage-api client", () => {
  beforeEach(() => {
    // Force live failure by default so tests are deterministic offline.
    setUsageFetch(() => Promise.reject(new Error("offline")));
  });

  afterEach(() => {
    setUsageFetch((...args) => fetch(...args));
  });

  it("normalizes a live summary payload into the typed shape", async () => {
    // Backend-ish payload: unsorted days, one metric as a numeric string.
    const livePayload = {
      days: [
        { date: "2026-07-21", sessions: 4, skill_runs: 2, scanner_runs: 1, briefs: 1 },
        { date: "2026-07-20", sessions: "3", skill_runs: 1, scanner_runs: 0, briefs: 2 },
      ],
      totals: { sessions: 7, skill_runs: 3, scanner_runs: 1, briefs: 3 },
    };
    setUsageFetch(
      () =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(livePayload),
        }) as unknown as ReturnType<typeof fetch>,
    );

    const { summary, source } = await getUsageSummary(2);
    expect(source).toBe("live");
    expect(summary.days).toHaveLength(2);
    // Sorted oldest-first regardless of wire order.
    expect(summary.days[0]?.date).toBe("2026-07-20");
    expect(summary.days[1]?.date).toBe("2026-07-21");
    for (const day of summary.days) {
      expect(typeof day.date).toBe("string");
      expect(day.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      for (const k of DAY_KEYS) {
        expect(typeof day[k]).toBe("number");
        expect(Number.isInteger(day[k])).toBe(true);
        expect(day[k]).toBeGreaterThanOrEqual(0);
      }
    }
    // Numeric-string metric coerced, backend totals preserved.
    expect(summary.days[0]?.sessions).toBe(3);
    expect(summary.totals).toEqual({ sessions: 7, skill_runs: 3, scanner_runs: 1, briefs: 3 });
  });

  it("totals always equal the column sums of the day rows", async () => {
    // Mock fallback: totals are derived from the seeded day rows.
    const { summary, source } = await getUsageSummary();
    expect(source).toBe("mock");
    expect(summary.days).toHaveLength(USAGE_DEFAULT_DAYS);
    expectTotalsMatchDays(summary.totals, summary.days);

    // Live payload with missing totals: recomputed from the day rows so the
    // stat cards and the table can never disagree.
    setUsageFetch(
      () =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              days: [
                { date: "2026-07-19", sessions: 2, skill_runs: 1, scanner_runs: 3, briefs: 0 },
                { date: "2026-07-20", sessions: 5, skill_runs: 2, scanner_runs: 1, briefs: 4 },
              ],
            }),
        }) as unknown as ReturnType<typeof fetch>,
    );
    const { summary: liveSummary } = await getUsageSummary(2);
    expectTotalsMatchDays(liveSummary.totals, liveSummary.days);
    expect(liveSummary.totals).toEqual({ sessions: 7, skill_runs: 3, scanner_runs: 4, briefs: 4 });
  });

  it("falls back to the deterministic paper mock when the live API is unavailable", async () => {
    const { summary, source } = await getUsageSummary();
    expect(source).toBe("mock");
    expect(summary.days.length).toBe(USAGE_DEFAULT_DAYS);
    // Window is contiguous, ascending calendar days ending on the fixed anchor.
    for (let i = 1; i < summary.days.length; i += 1) {
      expect(summary.days[i]!.date > summary.days[i - 1]!.date).toBe(true);
    }
    expect(summary.days[summary.days.length - 1]?.date).toBe("2026-07-21");
    expectTotalsMatchDays(summary.totals, summary.days);
    for (const k of TOTAL_KEYS) expect(summary.totals[k]).toBeGreaterThan(0);

    // The fallback never rejects, even on HTTP errors.
    setUsageFetch(
      () =>
        Promise.resolve({ ok: false, status: 500 }) as unknown as ReturnType<typeof fetch>,
    );
    const retry = await getUsageSummary();
    expect(retry.source).toBe("mock");
    expect(retry.summary.days).toHaveLength(USAGE_DEFAULT_DAYS);
  });
});
