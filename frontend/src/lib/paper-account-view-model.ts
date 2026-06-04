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
  orderHistory: Array<{
    id: string;
    marketSlug: string;
    marketTitle: string;
    side: "BUY" | "SELL";
    outcome: "YES" | "NO";
    orderType: "limit" | "market";
    price: number | null;
    quantity: number;
    filledQuantity: number;
    remainingQuantity: number;
    filledNotional: number;
    averageFillPrice: number | null;
    status: string;
    createdAt: string;
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
    orderHistory: account.order_history.map((order) => ({
      id: order.id,
      marketSlug: order.market_slug,
      marketTitle: order.market_title,
      side: order.side.toUpperCase() as "BUY" | "SELL",
      outcome: order.outcome.toUpperCase() as "YES" | "NO",
      orderType: order.order_type,
      price: order.price === null ? null : Number(order.price),
      quantity: Number(order.quantity),
      filledQuantity: Number(order.filled_quantity),
      remainingQuantity: Number(order.remaining_quantity),
      filledNotional: Number(order.filled_notional),
      averageFillPrice:
        order.average_fill_price === null ? null : Number(order.average_fill_price),
      status: order.status,
      createdAt: order.created_at,
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
