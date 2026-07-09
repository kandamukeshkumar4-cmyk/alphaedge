import type { CLVRecord, SignalFeedItem, SignalsDashboard } from "./signals-dashboard-api";

export type SignalCardView = {
  id: string;
  marketName: string;
  signalTypeLabel: string;
  impliedEdgeLabel: string;
  sampleSizeLabel: string;
  provisional: boolean;
  provisionalNote: string | null;
  statusLabel: string;
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
    paperOnlyNote: "Research only — no bets placed in-app",
    llmExplanation: dashboard.llm_explanation,
    signalCards: dashboard.signals.map(signalCard),
    clvRows: dashboard.clv_records.map(clvRow),
    empty: dashboard.signals.length === 0 && dashboard.clv_records.length === 0,
  };
}

/** Prefer a real title; otherwise turn a slug into a readable sentence. */
export function formatMarketLabel(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "Unknown market";
  }
  if (looksLikeHumanTitle(trimmed)) {
    return trimmed;
  }
  return humanizeSlug(trimmed);
}

/** `delta:price_jump` → "Price jump" (not SCREAMING_SNAKE). */
export function formatSignalTypeLabel(value: string): string {
  const core = value.includes(":") ? (value.split(":").pop() ?? value) : value;
  const words = core
    .split(/[-_\s]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => part.toLowerCase());
  if (words.length === 0) {
    return "Signal";
  }
  return words
    .map((word, index) => (index === 0 ? capitalize(word) : word))
    .join(" ");
}

function signalCard(item: SignalFeedItem): SignalCardView {
  const provisional =
    item.provisional || (item.sample_size > 0 && item.sample_size < PROVISIONAL_THRESHOLD);
  const statusLabel = item.is_edge
    ? "Edge"
    : provisional
      ? "Needs more history"
      : "No edge yet";

  return {
    id: item.id,
    marketName: formatMarketLabel(item.market_name),
    signalTypeLabel: formatSignalTypeLabel(item.signal_type),
    impliedEdgeLabel:
      item.implied_edge === null ? "—" : `${(item.implied_edge * 100).toFixed(2)}%`,
    sampleSizeLabel: item.sample_size > 0 ? String(item.sample_size) : "—",
    provisional,
    provisionalNote: provisional
      ? `Not enough resolved bets to score this yet (under ${PROVISIONAL_THRESHOLD}).`
      : null,
    statusLabel,
    isEdge: item.is_edge,
    blockedLabel: item.is_edge
      ? null
      : provisional
        ? null
        : "No edge detected yet — track record has not cleared the honesty check.",
  };
}

function clvRow(record: CLVRecord): CLVRowView {
  return {
    market: formatMarketLabel(record.market_slug),
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
      "Research only — not financial advice. No bets placed in-app. Simulation APIs remain paper-only.",
    paperPnlLabel: "$0.00",
    winRateLabel: "0%",
    betCountLabel: "0",
    paperOnlyNote: "Research only — no bets placed in-app",
    llmExplanation: null,
    signalCards: [],
    clvRows: [],
    empty: true,
  };
}

function looksLikeHumanTitle(value: string): boolean {
  if (/\s/.test(value) || value.includes("?")) {
    return true;
  }
  // Slug-like: mostly lowercase tokens joined by hyphens/underscores.
  if (/^[\w.-]+$/.test(value) && /[-_]/.test(value) && value === value.toLowerCase()) {
    return false;
  }
  return !/[-_]/.test(value);
}

function humanizeSlug(slug: string): string {
  let text = slug;
  text = text.replace(/^(pm|ks|kalshi|polymarket)[-_]+/i, "");
  // Drop trailing opaque ids (hex hashes or long numeric suffixes).
  text = text.replace(/[-_][a-f0-9]{8,}$/i, "");
  text = text.replace(/[-_]\d{6,}$/i, "");
  text = text.replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
  if (!text) {
    return slug;
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function capitalize(word: string): string {
  if (!word) {
    return word;
  }
  return word.charAt(0).toUpperCase() + word.slice(1);
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
