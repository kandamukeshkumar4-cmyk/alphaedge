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
  settled?: boolean;
  current_price?: number | null;
  unrealized_pnl?: number | null;
  pnl_pct?: number | null;
};

export type PortfolioView = {
  paper_balance: number;
  positions: PortfolioPosition[];
  realized_pnl: number;
  unrealized_pnl: number;
  portfolio_value: number;
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
  settled?: boolean;
  current_price?: number | null;
  unrealized_pnl?: number | null;
  pnl_pct?: number | null;
};

type RawPortfolioResponse = {
  paper_balance: number;
  positions: RawPortfolioPosition[];
  realized_pnl: number;
  unrealized_pnl?: number;
  portfolio_value?: number;
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
    unrealized_pnl: body.unrealized_pnl ?? 0,
    portfolio_value: body.portfolio_value ?? body.paper_balance,
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
      settled: position.settled ?? false,
      current_price: position.current_price ?? null,
      unrealized_pnl: position.unrealized_pnl ?? null,
      pnl_pct: position.pnl_pct ?? null,
    })),
  };
}

export type PortfolioSummary = {
  bankroll: number;
  open_positions: number;
  total_invested: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
};

export async function fetchPortfolioSummary(
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<PortfolioSummary | null> {
  const apiBase = (input?.apiBase ?? API_BASE).trim().replace(/\/+$/, "");
  if (!apiBase) return null;
  const fetcher = input?.fetcher ?? fetch;
  try {
    const response = await fetcher(`${apiBase}/api/v1/portfolio/summary`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as PortfolioSummary;
  } catch {
    return null;
  }
}

export type PortfolioRisk = {
  n_closed: number;
  total_realized_pnl: number;
  win_rate: number | null;
  max_drawdown: number;
  sharpe: number | null; // per-trade, NOT annualized
  exposure_by_category: Record<string, number>;
  exposure_pct_by_category: Record<string, number>;
  paper_trading_only: boolean;
  disclaimer: string;
};

export async function fetchPortfolioRisk(
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<PortfolioRisk | null> {
  const apiBase = (input?.apiBase ?? API_BASE).trim().replace(/\/+$/, "");
  if (!apiBase) return null;
  const fetcher = input?.fetcher ?? fetch;
  try {
    const response = await fetcher(`${apiBase}/api/v1/portfolio/risk`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as PortfolioRisk;
  } catch {
    return null;
  }
}

export type ExposureGroup = {
  underlier: string;
  position_count: number;
  net_directional: number;
  total_notional: number;
  pct_of_total: number;
  concentrated: boolean;
  positions: string[];
};

export type PortfolioExposure = {
  total_open_notional: number;
  groups: ExposureGroup[];
  has_concentration: boolean;
  concentrated_underliers: string[];
  paper_trading_only: boolean;
  disclaimer: string;
};

export async function fetchPortfolioExposure(
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<PortfolioExposure | null> {
  const apiBase = (input?.apiBase ?? API_BASE).trim().replace(/\/+$/, "");
  if (!apiBase) return null;
  const fetcher = input?.fetcher ?? fetch;
  try {
    const response = await fetcher(`${apiBase}/api/v1/portfolio/exposure`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as PortfolioExposure;
  } catch {
    return null;
  }
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
