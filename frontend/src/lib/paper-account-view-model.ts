import type { PaperAccountResponse } from "./paper-trading-api";
import type { PortfolioState } from "./portfolio-store";

export type PaperAccountView = {
  balance: number;
  availableCash: number;
  reservedCash: number;
  openOrders: Array<{
    id: string;
    marketSlug: string;
    marketTitle: string;
    side: "BUY" | "SELL";
    outcome: "YES" | "NO";
    price: number;
    remainingShares: number;
    reservedNotional: number;
    status: string;
  }>;
};

export function buildPaperAccountView(account: PaperAccountResponse): PaperAccountView {
  return {
    balance: Number(account.cash_balance),
    availableCash: Number(account.available_cash),
    reservedCash: Number(account.reserved_cash),
    openOrders: account.open_orders.map((order) => ({
      id: order.id,
      marketSlug: order.market_slug,
      marketTitle: order.market_title,
      side: order.side.toUpperCase() as "BUY" | "SELL",
      outcome: order.outcome.toUpperCase() as "YES" | "NO",
      price: Number(order.price ?? 0),
      remainingShares: Number(order.remaining_quantity),
      reservedNotional: Number(order.reserved_notional),
      status: order.status,
    })),
  };
}

export function selectDisplayedPortfolioState(
  localState: PortfolioState,
  accountView: PaperAccountView | null,
): PortfolioState {
  if (!accountView) {
    return localState;
  }

  return {
    balance: accountView.availableCash,
    positions: [],
    history: [],
  };
}
