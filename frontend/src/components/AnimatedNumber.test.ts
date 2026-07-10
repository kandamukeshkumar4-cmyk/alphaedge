import { describe, expect, it } from "vitest";
import { easeOutCubic } from "./AnimatedNumber";

describe("easeOutCubic", () => {
  it("anchors at 0 and 1", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
  });

  it("is front-loaded (past halfway by t=0.5)", () => {
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
  });

  it("is monotonically increasing", () => {
    let prev = -1;
    for (let t = 0; t <= 1; t += 0.1) {
      const v = easeOutCubic(t);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("clamps out-of-range input", () => {
    expect(easeOutCubic(-1)).toBe(0);
    expect(easeOutCubic(2)).toBe(1);
  });
});
