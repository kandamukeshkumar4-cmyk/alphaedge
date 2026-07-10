import { describe, expect, it } from "vitest";
import {
  buildTrackRecordView,
  formatClvBucketLabel,
  type PublicTrackRecord,
} from "./track-record-api";

const BASE: PublicTrackRecord = {
  n: 2,
  thin_data: true,
  thin_data_threshold: 30,
  brier_score: 0.065,
  calibration_bins: [
    { lower: 0.0, upper: 0.1, count: 0, mean_predicted: null, observed_frequency: null },
    { lower: 0.7, upper: 0.8, count: 1, mean_predicted: 0.7, observed_frequency: 1.0 },
    { lower: 0.2, upper: 0.3, count: 1, mean_predicted: 0.25, observed_frequency: 0.0 },
  ],
  brier_over_time: [
    { seq: 1, scored_at: "2026-07-09T16:00:00Z", brier: 0.09, cumulative_brier: 0.09 },
    { seq: 2, scored_at: "2026-07-09T17:00:00Z", brier: 0.04, cumulative_brier: 0.065 },
  ],
  clv: {
    count: 2,
    mean: -0.025,
    min: -0.12,
    max: 0.07,
    positive_share: 0.5,
    histogram: [
      { lower: null, upper: -0.2, count: 0 },
      { lower: -0.2, upper: -0.1, count: 1 },
      { lower: 0.05, upper: 0.1, count: 1 },
      { lower: 0.2, upper: null, count: 0 },
    ],
  },
  source: "forecast_scores",
  last_updated: "2026-07-09T17:00:00Z",
  paper_trading_only: true,
  disclaimer: "Research metrics from real resolutions only.",
};

describe("buildTrackRecordView", () => {
  it("marks honest empty when source is none", () => {
    const view = buildTrackRecordView({ ...BASE, source: "none", n: 0 });
    expect(view.available).toBe(false);
    expect(view.reliabilityPoints).toHaveLength(0);
    expect(view.caveat).toBeNull();
  });

  it("marks honest empty for a null response", () => {
    expect(buildTrackRecordView(null).available).toBe(false);
  });

  it("drops empty bins and sorts reliability points by predicted probability", () => {
    const view = buildTrackRecordView(BASE);
    expect(view.available).toBe(true);
    expect(view.reliabilityPoints).toEqual([
      { predicted: 0.25, observed: 0.0, count: 1 },
      { predicted: 0.7, observed: 1.0, count: 1 },
    ]);
    expect(view.hasReliability).toBe(true);
  });

  it("surfaces a prominent provisional caveat when thin_data is true", () => {
    const view = buildTrackRecordView(BASE);
    expect(view.caveat).toContain("Provisional (n=2)");
    expect(view.caveat).toContain("fewer than 30");
    expect(view.thinData).toBe(true);
  });

  it("omits the caveat when thin_data is false", () => {
    const view = buildTrackRecordView({ ...BASE, thin_data: false, n: 120 });
    expect(view.caveat).toBeNull();
  });

  it("labels brier and clv summary honestly", () => {
    const view = buildTrackRecordView(BASE);
    expect(view.brierLabel).toBe("0.065");
    expect(view.clvMeanLabel).toBe("-2.5%");
    expect(view.clvPositiveShareLabel).toBe("50%");
    expect(view.brierSeries).toHaveLength(2);
  });

  it("keeps a null brier honest", () => {
    const view = buildTrackRecordView({ ...BASE, brier_score: null });
    expect(view.brierLabel).toBe("—");
  });
});

describe("formatClvBucketLabel", () => {
  it("uses ≤ for an open lower tail", () => {
    expect(formatClvBucketLabel({ lower: null, upper: -0.2, count: 0 })).toBe("≤ -20%");
  });
  it("uses ≥ for an open upper tail", () => {
    expect(formatClvBucketLabel({ lower: 0.2, upper: null, count: 0 })).toBe("≥ 20%");
  });
  it("renders a bounded range", () => {
    expect(formatClvBucketLabel({ lower: -0.2, upper: -0.1, count: 1 })).toBe("-20…-10%");
  });
});
