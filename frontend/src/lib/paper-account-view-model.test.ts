import { describe, expect, it } from "vitest";

import { buildPaperAccountView, selectDisplayedPortfolioState } from "./paper-account-view-model";
import type { PaperAccountResponse } from "./paper-trading-api";
import type { PortfolioState } from "./portfolio-store";

const account: PaperAccountResponse = {
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
};

describe("paper account view model", () => {
  it("maps backend account cash and open orders into display numbers", () => {
    const view = buildPaperAccountView(account);

    expect(view).toEqual({
      balance: 100000,
      availableCash: 99994.5,
      reservedCash: 5.5,
      openOrders: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          marketSlug: "nba-2025-01-15-lal-bos",
          marketTitle: "Lakers vs Celtics",
          side: "BUY",
          outcome: "YES",
          price: 0.55,
          remainingShares: 10,
          reservedNotional: 5.5,
          status: "open",
        },
      ],
      orderHistory: [
        {
          id: "33333333-3333-3333-3333-333333333333",
          marketSlug: "nba-2025-01-15-lal-bos",
          marketTitle: "Lakers vs Celtics",
          side: "BUY",
          outcome: "YES",
          orderType: "market",
          price: null,
          quantity: 12,
          filledQuantity: 7,
          remainingQuantity: 5,
          filledNotional: 3.85,
          averageFillPrice: 0.55,
          status: "cancelled",
          createdAt: "2026-06-03T14:15:00.000Z",
        },
      ],
    });
  });

  it("uses backend account state instead of stale local demo positions", () => {
    const localState: PortfolioState = {
      balance: 99987,
      positions: [
        {
          id: "local-1",
          slug: "nba-2025-01-15-lal-bos",
          market: "Lakers vs Celtics",
          outcome: "Lakers",
          side: "YES",
          shares: 10,
          entryPrice: 0.65,
          currentPrice: 0.65,
          ts: 1,
        },
      ],
      history: [],
    };

    const display = selectDisplayedPortfolioState(localState, buildPaperAccountView(account));

    expect(display.balance).toBe(99994.5);
    expect(display.positions).toEqual([]);
    expect(display.history).toEqual([]);
  });
});
