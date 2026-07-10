import { describe, expect, it } from "vitest";
import { arbEmptyReason, type ArbOpportunitiesPage } from "./arb-api";

function page(overrides: Partial<ArbOpportunitiesPage>): ArbOpportunitiesPage {
  return {
    opportunities: [],
    total: 0,
    fresh_count: 0,
    stale_count: 0,
    signal_only: true,
    note: "",
    ...overrides,
  };
}

describe("arbEmptyReason", () => {
  it("explains an unreached backend for a null page", () => {
    expect(arbEmptyReason(null)).toContain("not reached");
  });

  it("explains all-stale when every matched quote is stale", () => {
    const reason = arbEmptyReason(page({ total: 2, stale_count: 2, fresh_count: 0 }));
    expect(reason).toContain("2 matched pairs");
    expect(reason).toContain("stale");
  });

  it("explains no matched pair when total is zero", () => {
    expect(arbEmptyReason(page({ total: 0 }))).toContain("No matched pair");
  });

  it("explains below-bar when pairs exist but none cleared", () => {
    const reason = arbEmptyReason(page({ total: 3, fresh_count: 3 }));
    expect(reason).toContain("none cleared the confidence and spread bar");
  });
});
