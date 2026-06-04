import { API_BASE } from "./alphaedge-api";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

const PAPER_ACCOUNT_TOKEN_KEY = "alphaedge.paperAccountToken.v1";
const PAPER_ACCOUNT_TOKEN_HEADER = "x-paper-account-token";
let memoryPaperAccountToken: string | null = null;

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

export type BackendOrderHistoryResponse = {
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
  filled_notional: string;
  average_fill_price: string | null;
  status: "open" | "partial" | "filled" | "cancelled";
  created_at: string;
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
  order_history: BackendOrderHistoryResponse[];
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
  paperAccountToken?: string;
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
      mode: "api";
      message: string;
    };

export type CancelPaperOrderInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  paperAccountToken?: string;
  orderId: string;
};

export type CancelPaperOrderResult =
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
    return backendUnavailable();
  }

  const fetcher = input.fetcher ?? fetch;
  const paperAccountToken = input.paperAccountToken ?? getPaperAccountToken();
  try {
    const account = await fetchPaperAccount({ apiBase, fetcher, paperAccountToken });
    if (!account) {
      return backendUnavailable();
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
      headers: paperAccountHeaders(paperAccountToken, { "content-type": "application/json" }),
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
    const updatedAccount =
      (await fetchPaperAccount({ apiBase, fetcher, paperAccountToken })) ?? account;
    return {
      ok: true,
      mode: "api",
      message: `Backend order accepted: ${order.status}`,
      order,
      account: updatedAccount,
    };
  } catch {
    return backendUnavailable();
  }
}

export async function cancelPaperOrder(
  input: CancelPaperOrderInput,
): Promise<CancelPaperOrderResult> {
  const apiBase = normalizeApiBase(input.apiBase ?? API_BASE);
  if (!apiBase) {
    return cancelFallback("local");
  }

  const fetcher = input.fetcher ?? fetch;
  const paperAccountToken = input.paperAccountToken ?? getPaperAccountToken();
  try {
    const account = await fetchPaperAccount({ apiBase, fetcher, paperAccountToken });
    if (!account) {
      return cancelFallback("local");
    }
    if (!account.paper_trading_only) {
      return {
        ok: false,
        mode: "api",
        message: "Backend is not in paper-trading mode.",
      };
    }

    const response = await fetcher(`${apiBase}/api/v1/orders/${input.orderId}/cancel`, {
      method: "POST",
      headers: paperAccountHeaders(paperAccountToken, { "content-type": "application/json" }),
      body: JSON.stringify({
        account_id: account.id,
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
    const updatedAccount =
      (await fetchPaperAccount({ apiBase, fetcher, paperAccountToken })) ?? account;
    return {
      ok: true,
      mode: "api",
      message: "Backend order cancelled.",
      order,
      account: updatedAccount,
    };
  } catch {
    return cancelFallback("api");
  }
}

export async function fetchPaperAccount(input?: {
  apiBase?: string;
  fetcher?: Fetcher;
  paperAccountToken?: string;
}): Promise<PaperAccountResponse | null> {
  const apiBase = normalizeApiBase(input?.apiBase ?? API_BASE);
  if (!apiBase) {
    return null;
  }

  try {
    return await fetchJson<PaperAccountResponse>(
      input?.fetcher ?? fetch,
      `${apiBase}/api/v1/paper-account`,
      { headers: paperAccountHeaders(input?.paperAccountToken ?? getPaperAccountToken()) },
    );
  } catch {
    return null;
  }
}

export function getPaperAccountToken(): string {
  const storage = safeLocalStorage();
  if (storage) {
    const existing = storage.getItem(PAPER_ACCOUNT_TOKEN_KEY);
    if (existing) {
      memoryPaperAccountToken = existing;
      return existing;
    }
    const token = randomToken();
    memoryPaperAccountToken = token;
    storage.setItem(PAPER_ACCOUNT_TOKEN_KEY, token);
    return token;
  }

  if (memoryPaperAccountToken) {
    return memoryPaperAccountToken;
  }

  const token = randomToken();
  memoryPaperAccountToken = token;
  return token;
}

async function fetchJson<T>(fetcher: Fetcher, url: string, init?: RequestInit): Promise<T> {
  const response = await fetcher(url, { ...init, cache: "no-store" });
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

function paperAccountHeaders(
  paperAccountToken: string,
  baseHeaders?: Record<string, string>,
): Record<string, string> {
  return {
    ...baseHeaders,
    [PAPER_ACCOUNT_TOKEN_HEADER]: paperAccountToken,
  };
}

function safeLocalStorage(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

function randomToken(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16);
    const nibble = char === "x" ? value : (value & 0x3) | 0x8;
    return nibble.toString(16);
  });
}

function backendUnavailable(): SubmitPaperOrderResult {
  return {
    ok: false,
    mode: "api",
    message: "Backend API unavailable; paper orders require the risk-gated backend.",
  };
}

function cancelFallback(mode: "api" | "local"): CancelPaperOrderResult {
  return {
    ok: false,
    mode,
    message: "Backend API unavailable; cannot cancel backend order.",
  };
}
