import { afterEach, describe, expect, it, vi } from "vitest";

import {
  cancelPaperOrder,
  fetchPaperAccount,
  getPaperAccountToken,
  resetPaperAccountSession,
  submitPaperOrder,
} from "./paper-trading-api";

describe("paper trading API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

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

  it("persists one browser paper account token and sends it on account and order calls", async () => {
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
    });
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    });

    const calls: Array<{ url: string; init?: RequestInit }> = [];
    let accountCalls = 0;
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/api/v1/paper-account")) {
        accountCalls += 1;
        return jsonResponse({
          id: "99999999-9999-9999-9999-999999999999",
          name: "Paper Session Account",
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
          account_id: "99999999-9999-9999-9999-999999999999",
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

    expect(getPaperAccountToken()).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    expect(getPaperAccountToken()).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");

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

    expect(result.ok).toBe(true);
    expect(crypto.randomUUID).toHaveBeenCalledTimes(1);
    expect(localStorage.setItem).toHaveBeenCalledTimes(1);
    for (const call of calls) {
      expect(headersObject(call.init?.headers)["x-paper-account-token"]).toBe(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      );
    }
  });

  it("rotates the browser paper account token and loads a fresh session account", async () => {
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
    });
    vi.stubGlobal("crypto", {
      randomUUID: vi
        .fn()
        .mockReturnValueOnce("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        .mockReturnValueOnce("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
    });

    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("https://api.example.test/api/v1/paper-account");
      expect(headersObject(init?.headers)["x-paper-account-token"]).toBe(
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      );
      return jsonResponse({
        id: "77777777-7777-7777-7777-777777777777",
        name: "Paper Session Account",
        cash_balance: "100000.0000",
        reserved_cash: "0.0000",
        available_cash: "100000.0000",
        paper_trading_only: true,
        positions: [],
        open_orders: [],
        order_history: [],
      });
    });

    expect(getPaperAccountToken()).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");

    const account = await resetPaperAccountSession({
      apiBase: "https://api.example.test",
      fetcher,
    });

    expect(account).toMatchObject({
      id: "77777777-7777-7777-7777-777777777777",
      available_cash: "100000.0000",
      reserved_cash: "0.0000",
      open_orders: [],
      order_history: [],
    });
    expect(getPaperAccountToken()).toBe("cccccccc-cccc-4ccc-8ccc-cccccccccccc");
    expect(localStorage.setItem).toHaveBeenCalledTimes(2);
    expect(crypto.randomUUID).toHaveBeenCalledTimes(2);
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

  it("allows callers to pass an explicit paper account token", async () => {
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("https://api.example.test/api/v1/paper-account");
      expect(headersObject(init?.headers)["x-paper-account-token"]).toBe(
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      );
      return jsonResponse({
        id: "88888888-8888-8888-8888-888888888888",
        name: "Paper Session Account",
        cash_balance: "100000.0000",
        reserved_cash: "0.0000",
        available_cash: "100000.0000",
        paper_trading_only: true,
        positions: [],
        open_orders: [],
        order_history: [],
      });
    });

    const account = await fetchPaperAccount({
      apiBase: "https://api.example.test",
      fetcher,
      paperAccountToken: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    });

    expect(account?.id).toBe("88888888-8888-8888-8888-888888888888");
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

function headersObject(headers: HeadersInit | undefined): Record<string, string> {
  return Object.fromEntries(new Headers(headers).entries());
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
