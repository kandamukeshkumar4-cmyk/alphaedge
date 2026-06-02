import { describe, expect, it, vi } from "vitest";

import { submitPaperOrder } from "./paper-trading-api";

describe("paper trading API", () => {
  it("loads the paper account and submits a risk-gated backend order", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/api/v1/paper-account")) {
        return jsonResponse({
          id: "00000000-0000-0000-0000-000000000001",
          name: "System Paper Account",
          cash_balance: "100000.0000",
          paper_trading_only: true,
          positions: [],
        });
      }
      if (url.endsWith("/api/v1/markets/nba-2025-01-15-lal-bos/orders")) {
        return jsonResponse({
          id: "11111111-1111-1111-1111-111111111111",
          market_id: "22222222-2222-2222-2222-222222222222",
          account_id: "00000000-0000-0000-0000-000000000001",
          side: "buy",
          outcome: "yes",
          order_type: "limit",
          price: "0.55",
          quantity: "10",
          filled_quantity: "0",
          status: "open",
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    });

    const result = await submitPaperOrder({
      apiBase: "https://api.example.test",
      fetcher,
      slug: "nba-2025-01-15-lal-bos",
      side: "YES",
      shares: 10,
      price: 0.55,
      forecast: {
        predictedProb: 0.62,
        confidence: 0.8,
        edge: 0.07,
      },
      minutesBeforeStart: 120,
      currentDrawdown: 0.02,
    });

    expect(result).toMatchObject({
      ok: true,
      mode: "api",
      message: "Backend order accepted: open",
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(calls[1].url).toBe(
      "https://api.example.test/api/v1/markets/nba-2025-01-15-lal-bos/orders",
    );
    expect(JSON.parse(String(calls[1].init?.body))).toEqual({
      account_id: "00000000-0000-0000-0000-000000000001",
      side: "buy",
      outcome: "yes",
      order_type: "limit",
      quantity: "10",
      price: "0.55",
      risk: {
        predicted_prob: 0.62,
        confidence: 0.8,
        edge: 0.07,
        current_drawdown: 0.02,
        minutes_before_start: 120,
      },
    });
  });

  it("returns a local fallback signal when no API base is configured", async () => {
    const result = await submitPaperOrder({
      apiBase: "",
      fetcher: vi.fn(),
      slug: "nba-2025-01-15-lal-bos",
      side: "NO",
      shares: 5,
      price: 0.45,
      forecast: {
        predictedProb: 0.42,
        confidence: 0.75,
        edge: 0.06,
      },
      minutesBeforeStart: 90,
      currentDrawdown: 0,
    });

    expect(result).toEqual({
      ok: false,
      mode: "local",
      message: "Backend API unavailable; use local paper fill fallback.",
    });
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
