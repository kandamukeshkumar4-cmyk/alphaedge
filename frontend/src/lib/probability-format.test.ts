import { describe, expect, it } from "vitest";

import { formatProbabilityAxis } from "./probability-format";

describe("probability formatting", () => {
  it("formats fractional probabilities as whole percentages for chart axes", () => {
    expect(formatProbabilityAxis(0.58)).toBe("58%");
    expect(formatProbabilityAxis(0.423)).toBe("42%");
    expect(formatProbabilityAxis(0.005)).toBe("1%");
  });
});
