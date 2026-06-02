import { API_BASE } from "./alphaedge-api";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type BackendOpenOrderResponse = {
  id: string;
  market_id: string;
  market_slug: string;
  market_title: string;
  side: "buy" | "sell";
  outcome: "yes" | "no";
  order_type: "limit" | "market";
  price: string | null;
  quantity: string;
  filled_quantity: string;
  remaining_quantity: string;
  reserved_notional: string;
  status: "open" | "partial" | "filled" | "cancelled";
};

export type PaperAccountResponse = {
  id: string;
  name: string;
  cash_balance: string;
  reserved_cash: string;
  available_cash: string;
  paper_trading_only: boolean;
  positions: unknown[];
  open_orders: BackendOpenOrderResponse[];
};

type BackendOrderResponse = {
  id: string;
  market_id: string;
  account_id: string;
  side: "buy" | "sell";
  outcome: "yes" | "no";
  order_type: "limit" | "market";
  price: string | null;
  quantity: string;
  filled_quantity: string;
  status: string;
};

export type SubmitPaperOrderInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  slug: string;
  side: "YES" | "NO";
  shares: number;
  price: number;
  forecast: {
    predictedProb: number;
    confidence: number;
    edge: number;
  };
  currentDrawdown: number;
  minutesBeforeStart: number;
};

export type SubmitPaperOrderResult =
  | {
      ok: true;
      mode: "api";
      message: string;
      order: BackendOrderResponse;
      account: PaperAccountResponse;
    }
  | {
      ok: false;
      mode: "api" | "local";
      message: string;
    };

export async function submitPaperOrder(
  input: SubmitPaperOrderInput,
): Promise<SubmitPaperOrderResult> {
  const apiBase = normalizeApiBase(input.apiBase ?? API_BASE);
  if (!apiBase) {
    return localFallback();
  }

  const fetcher = input.fetcher ?? fetch;
  try {
    const account = await fetchPaperAccount({ apiBase, fetcher });
    if (!account) {
      return localFallback();
    }
    if (!account.paper_trading_only) {
      return {
        ok: false,
        mode: "api",
        message: "Backend is not in paper-trading mode.",
      };
    }

    const response = await fetcher(`${apiBase}/api/v1/markets/${input.slug}/orders`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        account_id: account.id,
        side: "buy",
        outcome: input.side.toLowerCase(),
        order_type: "limit",
        quantity: decimalString(input.shares),
        price: decimalString(input.price),
        risk: {
          predicted_prob: input.forecast.predictedProb,
          confidence: input.forecast.confidence,
          edge: input.forecast.edge,
          current_drawdown: input.currentDrawdown,
          minutes_before_start: input.minutesBeforeStart,
        },
      }),
    });

    if (!response.ok) {
      return {
        ok: false,
        mode: "api",
        message: await errorMessage(response),
      };
    }

    const order = (await response.json()) as BackendOrderResponse;
    const updatedAccount = (await fetchPaperAccount({ apiBase, fetcher })) ?? account;
    return {
      ok: true,
      mode: "api",
      message: `Backend order accepted: ${order.status}`,
      order,
      account: updatedAccount,
    };
  } catch {
    return localFallback();
  }
}

export async function fetchPaperAccount(input?: {
  apiBase?: string;
  fetcher?: Fetcher;
}): Promise<PaperAccountResponse | null> {
  const apiBase = normalizeApiBase(input?.apiBase ?? API_BASE);
  if (!apiBase) {
    return null;
  }

  try {
    return await fetchJson<PaperAccountResponse>(
      input?.fetcher ?? fetch,
      `${apiBase}/api/v1/paper-account`,
    );
  } catch {
    return null;
  }
}

async function fetchJson<T>(fetcher: Fetcher, url: string): Promise<T> {
  const response = await fetcher(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return (await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Fall through to generic HTTP status text.
  }
  return response.statusText || `HTTP ${response.status}`;
}

function normalizeApiBase(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function decimalString(value: number): string {
  return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

function localFallback(): SubmitPaperOrderResult {
  return {
    ok: false,
    mode: "local",
    message: "Backend API unavailable; use local paper fill fallback.",
  };
}
