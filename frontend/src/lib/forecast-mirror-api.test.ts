import { describe, expect, it, vi } from "vitest";

import {
  createAnonymousForecaster,
  fetchForecastDashboard,
  lockForecast,
} from "./forecast-mirror-api";

describe("forecast mirror API", () => {
  it("creates an anonymous forecaster and preserves the one-time token", async () => {
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("https://api.example.test/api/v1/forecasters/anonymous");
      expect(init?.method).toBe("POST");
      return jsonResponse({
        id: "11111111-1111-1111-1111-111111111111",
        token: "raw-token-shown-once",
        disclaimer: "paper trading only",
      });
    });

    const forecaster = await createAnonymousForecaster({
      apiBase: "https://api.example.test/",
      fetcher,
    });

    expect(forecaster).toEqual({
      id: "11111111-1111-1111-1111-111111111111",
      token: "raw-token-shown-once",
      disclaimer: "paper trading only",
    });
  });

  it("locks a forecast against an external market through the backend ledger", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return jsonResponse({
        id: "22222222-2222-2222-2222-222222222222",
        external_market_id: "33333333-3333-3333-3333-333333333333",
        seq: 7,
        user_probability: 0.64,
        market_implied_probability: 0.58,
        is_independent: true,
        mode: "live",
        source: "web",
        time_to_resolution_seconds: 86400,
        locked_at: "2026-06-04T15:00:00Z",
        disclaimer: "paper trading only",
      });
    });

    const forecast = await lockForecast({
      apiBase: "https://api.example.test",
      fetcher,
      token: "forecaster-token",
      url: "https://polymarket.com/event/lakers-celtics",
      userProbability: 0.64,
      marketImpliedProbability: 0.58,
      mode: "live",
      snapshotSource: "manual",
    });

    expect(forecast).toMatchObject({
      id: "22222222-2222-2222-2222-222222222222",
      seq: 7,
      user_probability: 0.64,
      market_implied_probability: 0.58,
      is_independent: true,
    });
    expect(calls[0].url).toBe("https://api.example.test/api/v1/forecasts");
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      token: "forecaster-token",
      url: "https://polymarket.com/event/lakers-celtics",
      user_probability: 0.64,
      market_implied_probability: 0.58,
      snapshot_source: "manual",
      mode: "live",
      source: "web",
    });
  });

  it("loads the dashboard with the forecaster token header", async () => {
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("https://api.example.test/api/v1/forecasters/me/dashboard");
      expect(init?.headers).toEqual({
        "X-Forecaster-Token": "forecaster-token",
      });
      return jsonResponse({
        forecaster_id: "11111111-1111-1111-1111-111111111111",
        paper_trading_only: true,
        disclaimer: "paper trading only",
        live: {
          resolved_count: 6,
          unresolved_count: 3,
          independent_count: 5,
          anchored_count: 1,
          mean_user_brier: 0.18,
          mean_market_brier: 0.21,
          mean_brier_delta: -0.03,
          synthetic_pnl_total: 12.5,
          brier_provisional: false,
          calibration_provisional: true,
        },
        practice: {
          resolved_count: 4,
          mean_user_brier: 0.2,
          mean_brier_delta: -0.01,
        },
        calibration: [
          {
            lower: 0.5,
            upper: 0.6,
            count: 2,
            mean_predicted: 0.55,
            observed_frequency: 0.5,
          },
        ],
        category_breakdown: [
          {
            category: "Sports",
            count: 4,
            mean_brier_delta: -0.04,
          },
        ],
      });
    });

    const dashboard = await fetchForecastDashboard({
      apiBase: "https://api.example.test",
      fetcher,
      token: "forecaster-token",
    });

    expect(dashboard).toMatchObject({
      paper_trading_only: true,
      live: {
        resolved_count: 6,
        unresolved_count: 3,
        mean_brier_delta: -0.03,
      },
      calibration: [
        {
          count: 2,
          observed_frequency: 0.5,
        },
      ],
    });
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
