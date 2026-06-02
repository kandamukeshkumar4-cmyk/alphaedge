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
