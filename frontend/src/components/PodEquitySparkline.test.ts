import { describe, expect, it } from "vitest";

import { toSparklineSeries } from "./PodEquitySparkline";

// Loop V71 — never feed lightweight-charts NaN timestamps from bad ISO strings.

describe("toSparklineSeries (loop71)", () => {
  it("filters points whose timestamps are NaN before setData", () => {
    const series = toSparklineSeries([
      { t: "not-a-date", equity: 100 },
      { t: "2026-07-17T10:00:00Z", equity: 110 },
      { t: "bogus", equity: 120 },
      { t: "2026-07-17T11:00:00Z", equity: 130 },
    ]);

    expect(series).toHaveLength(2);
    expect(series.every((p) => Number.isFinite(p.time as number))).toBe(true);
    expect(series.map((p) => p.value)).toEqual([110, 130]);
  });

  it("dedupes identical ascending timestamps", () => {
    const series = toSparklineSeries([
      { t: "2026-07-17T10:00:00Z", equity: 100 },
      { t: "2026-07-17T10:00:00Z", equity: 105 },
      { t: "2026-07-17T11:00:00Z", equity: 110 },
    ]);

    expect(series).toHaveLength(2);
    expect(series.map((p) => p.value)).toEqual([100, 110]);
  });
});
