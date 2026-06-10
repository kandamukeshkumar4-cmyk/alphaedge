import { API_BASE } from "./alphaedge-api";

export const PORTFOLIO_DISCLAIMER =
  "Research only — not financial advice. Verify resolution terms. Paper trading only.";

export const ACCESS_TOKEN_KEY = "alphaedge.accessToken";

export type PortfolioPosition = {
  id: string;
  market_slug: string;
  market_title: string;
  side: string;
  outcome: string;
  quantity: number;
  price: number | null;
  realized_pnl?: number | null;
};

export type PortfolioView = {
  paper_balance: number;
  positions: PortfolioPosition[];
  realized_pnl: number;
  total_trades: number;
  paper_trading_only: boolean;
  disclaimer: string;
};

export type OrderHistoryItem = {
  slug: string;
  outcome: string;
  side: string;
  shares: number;
  price: number;
  cost: number;
  settled: boolean;
  created_at: string;
};

type RawPortfolioPosition = {
  id?: string | null;
  market_slug: string;
  market_title?: string;
  side: string;
  outcome?: string;
  shares: number;
  avg_cost: number;
  cost: number;
  realized_pnl?: number | null;
};

type RawPortfolioResponse = {
  paper_balance: number;
  positions: RawPortfolioPosition[];
  realized_pnl: number;
  total_trades: number;
  paper_trading_only: boolean;
  disclaimer: string;
};

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export function getAccessToken(): string | null {
  try {
    return typeof localStorage === "undefined"
      ? null
      : localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function fetchPortfolio(
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<PortfolioView> {
  const apiBase = (input?.apiBase ?? API_BASE).trim().replace(/\/+$/, "");
  if (!apiBase) {
    throw new Error("Set NEXT_PUBLIC_API_URL to load your portfolio.");
  }

  const fetcher = input?.fetcher ?? fetch;
  const response = await fetcher(`${apiBase}/api/v1/portfolio`, {
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    let detail = response.statusText || `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Keep generic status text.
    }
    throw new Error(detail);
  }

  const body = (await response.json()) as RawPortfolioResponse;

  return {
    paper_balance: body.paper_balance,
    realized_pnl: body.realized_pnl,
    total_trades: body.total_trades,
    paper_trading_only: body.paper_trading_only,
    disclaimer: body.disclaimer,
    positions: body.positions.map((position) => ({
      id:
        position.id ??
        `${position.market_slug}:${position.side}:${position.outcome ?? "yes"}`,
      market_slug: position.market_slug,
      market_title: position.market_title ?? position.market_slug,
      side: position.side,
      outcome: position.outcome ?? "yes",
      quantity: position.shares,
      price: position.avg_cost,
      realized_pnl: position.realized_pnl ?? null,
    })),
  };
}

export async function fetchOrderHistory(
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<OrderHistoryItem[]> {
  const apiBase = (input?.apiBase ?? API_BASE).trim().replace(/\/+$/, "");
  if (!apiBase) {
    throw new Error("Set NEXT_PUBLIC_API_URL to load trade history.");
  }

  const fetcher = input?.fetcher ?? fetch;
  const response = await fetcher(`${apiBase}/api/v1/orders/history`, {
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    let detail = response.statusText || `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Keep generic status text.
    }
    throw new Error(detail);
  }

  return (await response.json()) as OrderHistoryItem[];
}
