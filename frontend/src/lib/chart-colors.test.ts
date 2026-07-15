import { describe, expect, it } from "vitest";

import {
  CHART_COLOR_FALLBACKS,
  chartRgb,
  chartRgba,
  cssColorTriplet,
  hexToTriplet,
  readLwcChartTheme,
} from "./chart-colors";

describe("chart-colors (canvas-safe color resolution)", () => {
  it("falls back to the concrete triplet when there is no DOM", () => {
    // vitest runs in node env — document is undefined, so the fallback path
    // must produce a fully concrete color.
    expect(cssColorTriplet("--color-primary", CHART_COLOR_FALLBACKS.primary)).toBe(
      "0, 232, 176",
    );
  });

  it("never emits a CSS var() reference (canvas would throw)", () => {
    const rgb = chartRgb("--color-primary", CHART_COLOR_FALLBACKS.primary);
    const rgba = chartRgba("--color-danger", CHART_COLOR_FALLBACKS.danger, 0.25);
    expect(rgb).toBe("rgb(0, 232, 176)");
    expect(rgba).toBe("rgba(255, 90, 95, 0.25)");
    expect(rgb).not.toContain("var(");
    expect(rgba).not.toContain("var(");
  });

  it("converts hex token values to rgb triplets", () => {
    expect(hexToTriplet("#00E8B0")).toBe("0, 232, 176");
    expect(hexToTriplet("#fff")).toBe("255, 255, 255");
    expect(hexToTriplet("not-a-color")).toBeNull();
  });

  it("readLwcChartTheme returns concrete rgb/rgba strings (SSR fallback)", () => {
    const theme = readLwcChartTheme();
    expect(theme.text).toBe(`rgb(${CHART_COLOR_FALLBACKS.text})`);
    expect(theme.accent).toBe(`rgb(${CHART_COLOR_FALLBACKS.primary})`);
    expect(theme.grid).toContain("rgba(");
    expect(theme.text).not.toContain("var(");
    expect(theme.grid).not.toContain("var(");
  });
});
