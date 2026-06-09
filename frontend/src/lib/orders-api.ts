import { API_BASE } from "./alphaedge-api";

export const ACCESS_TOKEN_KEY = "alphaedge.accessToken";

export type PaperOrderInput = {
  slug: string;
  side: "YES" | "NO";
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
  const apiBase = API_BASE || "http://localhost:8000";
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
