import { afterEach, describe, expect, it, vi } from "vitest";

import { buildCalibrationCurve, type CalibrationBin, fetchCalibrationBins } from "./calibration-api";

function bin(binIdx: number, count: number, pred: number, outcome: number): CalibrationBin {
  return { bin: binIdx, count, mean_pred: pred, mean_outcome: outcome };
}

describe("buildCalibrationCurve", () => {
  it("drops empty bins and maps real predicted/observed/n", () => {
    const bins = [
      bin(0, 0, 0, 0),
      bin(2, 40, 0.25, 0.2),
      bin(7, 30, 0.75, 0.8),
      bin(9, 0, 0, 0),
    ];
    const curve = buildCalibrationCurve(bins, 50);
    expect(curve.points).toEqual([
      { predicted: 0.25, observed: 0.2, n: 40 },
      { predicted: 0.75, observed: 0.8, n: 30 },
    ]);
    expect(curve.totalN).toBe(70);
    // 70 >= 50 threshold → not provisional
    expect(curve.provisional).toBe(false);
  });

  it("sorts points by predicted probability", () => {
    const bins = [bin(8, 5, 0.85, 0.9), bin(1, 5, 0.15, 0.1)];
    const curve = buildCalibrationCurve(bins, 50);
    expect(curve.points.map((p) => p.predicted)).toEqual([0.15, 0.85]);
  });

  it("labels thin data provisional when total n is below the threshold", () => {
    const curve = buildCalibrationCurve([bin(3, 10, 0.35, 0.3)], 50);
    expect(curve.totalN).toBe(10);
    expect(curve.provisional).toBe(true);
  });

  it("returns an empty, provisional curve for no bins", () => {
    const curve = buildCalibrationCurve([]);
    expect(curve.points).toEqual([]);
    expect(curve.totalN).toBe(0);
    expect(curve.provisional).toBe(true);
  });
});

describe("fetchCalibrationBins", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("calibration_bins_fetches_the_eval_calibration_path", async () => {
    const bins: CalibrationBin[] = [{ bin: 0, count: 2, mean_pred: 0.1, mean_outcome: 0.2 }];
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ bins }),
    } as Response);
    vi.stubGlobal("fetch", fetcher);

    // Parsing is untouched: the bins array comes back verbatim.
    await expect(fetchCalibrationBins()).resolves.toEqual(bins);

    const urls = fetcher.mock.calls.map((call) => String(call[0]));
    // The request must target the real eval endpoint…
    expect(urls.some((url) => /\/api\/v1\/eval\/calibration(\?|$)/.test(url))).toBe(true);
    // …and never the bare /api/v1/calibration path that 404s in prod.
    expect(urls.some((url) => /\/api\/v1\/calibration(\?|$)/.test(url))).toBe(false);
  });

  it("calibration_bins_returns_empty_on_http_error", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response);
    vi.stubGlobal("fetch", fetcher);

    await expect(fetchCalibrationBins()).resolves.toEqual([]);
  });
});
