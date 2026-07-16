import { describe, expect, it } from "vitest";
import {
  buildModelAbView,
  buildResolvedCountDisclosure,
  type ModelAbResponse,
  type ResolvedCountResponse,
} from "./model-ab-api";

const RESOLVED_LOW: ResolvedCountResponse = {
  resolved_count: 42,
  ab_threshold: 100,
  ab_ready: false,
  model_default: "xgboost",
  paper_trading_only: true,
  source: "paper_orders_fallback",
  forecast_scored_count: 0,
};

const RESOLVED_READY: ResolvedCountResponse = {
  ...RESOLVED_LOW,
  resolved_count: 120,
  ab_ready: true,
  source: "forecast_scores",
  forecast_scored_count: 120,
};

describe("buildResolvedCountDisclosure", () => {
  it("returns null when resolved-count is missing", () => {
    expect(buildResolvedCountDisclosure(null)).toBeNull();
  });

  it("labels scored LIVE forecasts honestly", () => {
    const view = buildResolvedCountDisclosure(RESOLVED_READY);
    expect(view?.source).toBe("forecast_scores");
    expect(view?.forecastScoredCount).toBe(120);
    expect(view?.resolvedCount).toBe(120);
    expect(view?.isPaperOrdersFallback).toBe(false);
    expect(view?.sourceLabel).toContain("Scored LIVE");
  });

  it("discloses paper-order fallback when scored count is zero", () => {
    const view = buildResolvedCountDisclosure(RESOLVED_LOW);
    expect(view?.source).toBe("paper_orders_fallback");
    expect(view?.forecastScoredCount).toBe(0);
    expect(view?.isPaperOrdersFallback).toBe(true);
    expect(view?.sourceDetail).toContain("different population");
  });

  it("does not fabricate source or scored count when absent", () => {
    const view = buildResolvedCountDisclosure({
      resolved_count: 3,
      ab_threshold: 100,
      ab_ready: false,
      model_default: "xgboost",
      paper_trading_only: true,
    });
    expect(view?.source).toBeNull();
    expect(view?.forecastScoredCount).toBeNull();
    expect(view?.sourceLabel).toBe("Source undisclosed");
  });
});

describe("buildModelAbView — not ready", () => {
  it("shows progress toward the threshold and never claims a winner", () => {
    const view = buildModelAbView({ ready: false, resolved_count: 42, threshold: 100 }, RESOLVED_LOW);
    expect(view.state).toBe("not-ready");
    expect(view.progressPct).toBeCloseTo(42, 5);
    expect(view.remaining).toBe(58);
    expect(view.resolvedLabel).toBe("42 / 100 resolved");
    expect(view.winnerLabel).toBeNull();
    expect(view.defaultUnchanged).toBe(true);
  });

  it("is loading when both inputs are null", () => {
    expect(buildModelAbView(null, null).state).toBe("loading");
  });
});

describe("buildModelAbView — ready", () => {
  const ab: ModelAbResponse = {
    ready: true,
    lightgbm_available: true,
    xgb_brier: 0.18,
    lgbm_brier: 0.21,
    which_would_win: "xgboost",
    applied: false,
    model_default: "xgboost",
  };

  it("shows both Briers, delta, and the would-win model", () => {
    const view = buildModelAbView(ab, RESOLVED_READY);
    expect(view.state).toBe("ready");
    expect(view.xgbBrierLabel).toBe("0.1800");
    expect(view.lgbmBrierLabel).toBe("0.2100");
    expect(view.deltaLabel).toBe("-0.0300"); // xgb - lgbm
    expect(view.winnerLabel).toBe("Xgboost");
    expect(view.progressPct).toBe(100);
    expect(view.defaultUnchanged).toBe(true);
  });

  it("derives the winner when the backend omits which_would_win", () => {
    const view = buildModelAbView(
      { ...ab, which_would_win: null, delta: null },
      RESOLVED_READY,
    );
    expect(view.winnerLabel).toBe("Xgboost"); // 0.18 < 0.21
  });
});

describe("buildModelAbView — lightgbm unavailable", () => {
  it("reports XGB-only with an honest note", () => {
    const view = buildModelAbView(
      { ready: true, lightgbm_available: false, xgb_brier: 0.19, lgbm_brier: null },
      RESOLVED_READY,
    );
    expect(view.state).toBe("lgbm-unavailable");
    expect(view.xgbBrierLabel).toBe("0.1900");
    expect(view.lgbmBrierLabel).toBe("—");
    expect(view.unavailableNote).toContain("LightGBM is not available");
    expect(view.defaultUnchanged).toBe(true);
  });

  it("treats a missing lgbm_brier as unavailable even if the flag is absent", () => {
    const view = buildModelAbView({ ready: true, xgb_brier: 0.2 }, RESOLVED_READY);
    expect(view.state).toBe("lgbm-unavailable");
  });
});
