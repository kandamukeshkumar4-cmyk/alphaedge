import type { CLVRecord, SignalFeedItem, SignalsDashboard } from "./signals-dashboard-api";

export type SignalCardView = {
  id: string;
  marketName: string;
  signalTypeLabel: string;
  impliedEdgeLabel: string;
  sampleSize: number;
  provisional: boolean;
  isEdge: boolean;
  blockedLabel: string | null;
};

export type CLVRowView = {
  market: string;
  modelProbLabel: string;
  closingProbLabel: string;
  clvLabel: string;
  resolvedAtLabel: string;
  isEdge: boolean;
};

export type SignalsDashboardView = {
  disclaimer: string;
  paperPnlLabel: string;
  winRateLabel: string;
  betCountLabel: string;
  paperOnlyNote: string;
  llmExplanation: string | null;
  signalCards: SignalCardView[];
  clvRows: CLVRowView[];
  empty: boolean;
};

const PROVISIONAL_THRESHOLD = 30;

export function buildSignalsDashboardView(
  dashboard: SignalsDashboard | null,
): SignalsDashboardView {
  if (!dashboard) {
    return emptyView();
  }

  return {
    disclaimer: dashboard.disclaimer,
    paperPnlLabel: money(dashboard.paper_pnl.total_pnl),
    winRateLabel: pct(dashboard.paper_pnl.win_rate),
    betCountLabel: String(dashboard.paper_pnl.n_bets),
    paperOnlyNote: "Paper trading only — simulated funds",
    llmExplanation: dashboard.llm_explanation,
    signalCards: dashboard.signals.map(signalCard),
    clvRows: dashboard.clv_records.map(clvRow),
    empty: dashboard.signals.length === 0 && dashboard.clv_records.length === 0,
  };
}

function signalCard(item: SignalFeedItem): SignalCardView {
  const provisional =
    item.provisional || (item.sample_size > 0 && item.sample_size < PROVISIONAL_THRESHOLD);
  return {
    id: item.id,
    marketName: item.market_name,
    signalTypeLabel: formatSignalType(item.signal_type),
    impliedEdgeLabel:
      item.implied_edge === null ? "—" : `${(item.implied_edge * 100).toFixed(2)}%`,
    sampleSize: item.sample_size,
    provisional,
    isEdge: item.is_edge,
    blockedLabel: item.is_edge ? null : "No edge detected (CLV gate blocked)",
  };
}

function clvRow(record: CLVRecord): CLVRowView {
  return {
    market: record.market_slug,
    modelProbLabel: prob(record.model_prob),
    closingProbLabel: record.closing_prob === null ? "—" : prob(record.closing_prob),
    clvLabel: record.clv === null ? "—" : signedPct(record.clv),
    resolvedAtLabel: record.resolved_at
      ? new Date(record.resolved_at).toLocaleString()
      : "—",
    isEdge: record.is_edge,
  };
}

function emptyView(): SignalsDashboardView {
  return {
    disclaimer:
      "Research only — not financial advice. Verify resolution terms. Paper trading only.",
    paperPnlLabel: "$0.00",
    winRateLabel: "0%",
    betCountLabel: "0",
    paperOnlyNote: "Paper trading only — simulated funds",
    llmExplanation: null,
    signalCards: [],
    clvRows: [],
    empty: true,
  };
}

function formatSignalType(value: string): string {
  return value
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function prob(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function signedPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function money(value: number): string {
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}
