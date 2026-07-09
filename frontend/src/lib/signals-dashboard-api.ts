import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";

export const SIGNALS_DISCLAIMER =
  "Research only — not financial advice. Verify resolution terms. Paper trading only.";

export type SignalFeedItem = {
  id: string;
  signal_type: string;
  platform: string;
  market_id: string;
  market_name: string;
  implied_edge: number | null;
  sample_size: number;
  is_edge: boolean;
  provisional: boolean;
  created_at: string;
  resolved: boolean;
};

export type CLVRecord = {
  market_slug: string;
  model_prob: number;
  closing_prob: number | null;
  clv: number | null;
  resolved_at: string | null;
  is_edge: boolean;
};

export type PaperPnlSummary = {
  total_pnl: number;
  n_bets: number;
  win_rate: number;
  note: string;
  disclaimer: string;
  paper_trading_only: boolean;
};

export type SignalsDashboard = {
  paper_trading_only: boolean;
  disclaimer: string;
  signals: SignalFeedItem[];
  clv_records: CLVRecord[];
  paper_pnl: PaperPnlSummary;
  llm_explanation: string | null;
};

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export async function fetchSignalsDashboard(input?: {
  apiBase?: string;
  fetcher?: Fetcher;
}): Promise<SignalsDashboard | null> {
  // Empty apiBase is valid in browser prod (same-origin Vercel → HF rewrite).
  const apiBase = input?.apiBase ?? (await ensureApiBase()) ?? API_BASE;
  if (!hasLiveApi(apiBase)) {
    return null;
  }
  const fetcher = input?.fetcher ?? fetch;
  const response = await fetcher(apiUrl("/api/v1/signals/dashboard", apiBase), {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Signals dashboard HTTP ${response.status}`);
  }
  return (await response.json()) as SignalsDashboard;
}
