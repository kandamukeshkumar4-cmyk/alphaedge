import { API_BASE } from "./alphaedge-api";

export const ACCESS_TOKEN_KEY = "alphaedge.accessToken";

export type PaperOrderInput = {
  slug: string;
  side: "buy";
  outcome: "yes" | "no";
  shares: number;
  price: number;
};

export type PaperOrderResponse = {
  order_id: string;
  slug: string;
  side: "YES" | "NO";
  shares: number;
  cost: number;
  remaining_balance: number;
  paper_trading_only: true;
};

export async function placePaperOrder(
  token: string,
  order: PaperOrderInput,
): Promise<PaperOrderResponse> {
  const apiBase = API_BASE;
  const response = await fetch(`${apiBase}/api/v1/orders`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(order),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `Order request failed with HTTP ${response.status}`;
    throw new Error(detail);
  }

  return (await response.json()) as PaperOrderResponse;
}

export type PositionCloseInput = {
  slug: string;
  outcome: "yes" | "no";
  shares: number;
  price: number;
};

export type PositionCloseResponse = {
  order_id: string;
  slug: string;
  outcome: "yes" | "no";
  shares_sold: number;
  proceeds: number;
  realized_pnl: number;
  remaining_shares: number;
  remaining_balance: number;
  paper_trading_only: true;
};

export async function closePaperPosition(
  token: string,
  input: PositionCloseInput,
): Promise<PositionCloseResponse> {
  const apiBase = API_BASE;
  const response = await fetch(`${apiBase}/api/v1/positions/close`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `Close request failed with HTTP ${response.status}`;
    throw new Error(detail);
  }

  return (await response.json()) as PositionCloseResponse;
}
