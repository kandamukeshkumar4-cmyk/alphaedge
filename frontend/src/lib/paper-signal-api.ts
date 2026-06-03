import { API_BASE } from "./alphaedge-api";
import { fetchPaperAccount } from "./paper-trading-api";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type PaperSignalOutcome = "yes" | "no";

export type PaperSignalSummary = {
  paper_trading_only: boolean;
  market_id: string;
  market_slug: string;
  selected_outcome: PaperSignalOutcome | null;
  total_signals: number;
  options: Array<{
    outcome: PaperSignalOutcome;
    count: number;
    percentage: number;
  }>;
};

export type FetchPaperSignalSummaryInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  slug: string;
  accountId?: string;
};

export type SubmitPaperSignalInput = {
  apiBase?: string;
  fetcher?: Fetcher;
  slug: string;
  outcome: PaperSignalOutcome;
};

export type SubmitPaperSignalResult =
  | {
      ok: true;
      mode: "api";
      summary: PaperSignalSummary;
    }
  | {
      ok: false;
      mode: "api" | "local";
      message: string;
    };

export async function fetchPaperSignalSummary(
  input: FetchPaperSignalSummaryInput,
): Promise<PaperSignalSummary | null> {
  const apiBase = normalizeApiBase(input.apiBase ?? API_BASE);
  if (!apiBase) {
    return null;
  }

  const query = input.accountId ? `?account_id=${encodeURIComponent(input.accountId)}` : "";
  try {
    return await fetchJson<PaperSignalSummary>(
      input.fetcher ?? fetch,
      `${apiBase}/api/v1/markets/${input.slug}/signals${query}`,
    );
  } catch {
    return null;
  }
}

export async function submitPaperSignal(
  input: SubmitPaperSignalInput,
): Promise<SubmitPaperSignalResult> {
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

    const response = await fetcher(`${apiBase}/api/v1/markets/${input.slug}/signals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        account_id: account.id,
        outcome: input.outcome,
      }),
    });
    if (!response.ok) {
      return {
        ok: false,
        mode: "api",
        message: await errorMessage(response),
      };
    }

    return {
      ok: true,
      mode: "api",
      summary: (await response.json()) as PaperSignalSummary,
    };
  } catch {
    return {
      ok: false,
      mode: "api",
      message: "Backend API unavailable; cannot submit paper signal.",
    };
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

function localFallback(): SubmitPaperSignalResult {
  return {
    ok: false,
    mode: "local",
    message: "Backend API unavailable; use local paper signal fallback.",
  };
}
