import { describe, expect, it, vi } from "vitest";

import { cancelPaperOrder, fetchPaperAccount, submitPaperOrder } from "./paper-trading-api";

describe("paper trading API", () => {
  it("loads the paper account and submits a risk-gated backend order", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    let accountCalls = 0;
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/api/v1/paper-account")) {
        accountCalls += 1;
        return jsonResponse({
          id: "00000000-0000-0000-0000-000000000001",
          name: "System Paper Account",
          cash_balance: "100000.0000",
          reserved_cash: accountCalls === 1 ? "0.0000" : "5.5000",
          available_cash: accountCalls === 1 ? "100000.0000" : "99994.5000",
          paper_trading_only: true,
          positions: [],
          open_orders: [],
          order_history: [],
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
      account: {
        available_cash: "99994.5000",
        reserved_cash: "5.5000",
      },
    });
    expect(fetcher).toHaveBeenCalledTimes(3);
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

  it("fails closed when no API base is configured", async () => {
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
      mode: "api",
      message: "Backend API unavailable; paper orders require the risk-gated backend.",
    });
  });

  it("loads backend available cash and open paper orders", async () => {
    const fetcher = vi.fn(async (url: string) => {
      expect(url).toBe("https://api.example.test/api/v1/paper-account");
      return jsonResponse({
        id: "00000000-0000-0000-0000-000000000001",
        name: "System Paper Account",
        cash_balance: "100000.0000",
        reserved_cash: "5.5000",
        available_cash: "99994.5000",
        paper_trading_only: true,
        positions: [],
        open_orders: [
          {
            id: "11111111-1111-1111-1111-111111111111",
            market_id: "22222222-2222-2222-2222-222222222222",
            market_slug: "nba-2025-01-15-lal-bos",
            market_title: "Lakers vs Celtics",
            side: "buy",
            outcome: "yes",
            order_type: "limit",
            price: "0.5500",
            quantity: "10.0000",
            filled_quantity: "0.0000",
            remaining_quantity: "10.0000",
            reserved_notional: "5.5000",
            status: "open",
          },
        ],
        order_history: [
          {
            id: "33333333-3333-3333-3333-333333333333",
            market_id: "22222222-2222-2222-2222-222222222222",
            market_slug: "nba-2025-01-15-lal-bos",
            market_title: "Lakers vs Celtics",
            side: "buy",
            outcome: "yes",
            order_type: "market",
            price: null,
            quantity: "12.0000",
            filled_quantity: "7.0000",
            remaining_quantity: "5.0000",
            filled_notional: "3.8500",
            average_fill_price: "0.5500",
            status: "cancelled",
            created_at: "2026-06-03T14:15:00.000Z",
          },
        ],
      });
    });

    const account = await fetchPaperAccount({
      apiBase: "https://api.example.test",
      fetcher,
    });

    expect(account).toMatchObject({
      available_cash: "99994.5000",
      reserved_cash: "5.5000",
      open_orders: [
        {
          market_slug: "nba-2025-01-15-lal-bos",
          market_title: "Lakers vs Celtics",
          reserved_notional: "5.5000",
        },
      ],
      order_history: [
        {
          market_slug: "nba-2025-01-15-lal-bos",
          market_title: "Lakers vs Celtics",
          average_fill_price: "0.5500",
        },
      ],
    });
  });

  it("cancels a backend paper order and returns the refreshed account", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    let accountCalls = 0;
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/api/v1/paper-account")) {
        accountCalls += 1;
        return jsonResponse({
          id: "00000000-0000-0000-0000-000000000001",
          name: "System Paper Account",
          cash_balance: "100000.0000",
          reserved_cash: accountCalls === 1 ? "5.5000" : "0.0000",
          available_cash: accountCalls === 1 ? "99994.5000" : "100000.0000",
          paper_trading_only: true,
          positions: [],
          open_orders:
            accountCalls === 1
              ? [
                  {
                    id: "11111111-1111-1111-1111-111111111111",
                    market_id: "22222222-2222-2222-2222-222222222222",
                    market_slug: "nba-2025-01-15-lal-bos",
                    market_title: "Lakers vs Celtics",
                    side: "buy",
                    outcome: "yes",
                    order_type: "limit",
                    price: "0.5500",
                    quantity: "10.0000",
                    filled_quantity: "0.0000",
                    remaining_quantity: "10.0000",
                    reserved_notional: "5.5000",
                    status: "open",
                  },
                ]
              : [],
          order_history: [],
        });
      }
      if (url.endsWith("/api/v1/orders/11111111-1111-1111-1111-111111111111/cancel")) {
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
          status: "cancelled",
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    });

    const result = await cancelPaperOrder({
      apiBase: "https://api.example.test",
      fetcher,
      orderId: "11111111-1111-1111-1111-111111111111",
    });

    expect(result).toMatchObject({
      ok: true,
      mode: "api",
      message: "Backend order cancelled.",
      account: {
        available_cash: "100000.0000",
        reserved_cash: "0.0000",
        open_orders: [],
      },
    });
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(calls[1].url).toBe(
      "https://api.example.test/api/v1/orders/11111111-1111-1111-1111-111111111111/cancel",
    );
    expect(JSON.parse(String(calls[1].init?.body))).toEqual({
      account_id: "00000000-0000-0000-0000-000000000001",
    });
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
