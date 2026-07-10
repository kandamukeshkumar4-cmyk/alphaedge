import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import { type SmartMoney, buildSmartMoneyView, type SmartMoneyView } from "@/lib/smart-money-api";
import { extractSignalEvidence, type SignalEvidence } from "@/lib/signal-evidence";

/**
 * D01: single-call market intelligence — GET /api/v1/desk?slug= (backend H01).
 * Composes market snapshot + latest model edge + G07 smart-money summary +
 * G02 arb match + latest signal events in ONE response so the market page's
 * Intelligence panel does not fan out separate fetches. READ-ONLY analysis:
 * signal_only is always true; no order path. See goals/loop-v3/API-NOTES.md.
 */

export type DeskEdge = {
  predicted_prob: number;
  confidence: number | null;
  edge_vs_book: number | null;
  input_feature_hash: string | null;
  predicted_at: string | null;
  source: string;
};

export type DeskArb = {
  pm_slug: string;
  ks_slug: string;
  pm_title: string;
  ks_title: string;
  confidence: number | null;
  reasons: string[];
  stale: boolean;
  matched_at: string | null;
  updated_at: string | null;
};

export type DeskSignal = {
  id: string;
  signal_type: string;
  platform: string;
  market_id: string;
  headline_eligible: boolean;
  payload: Record<string, unknown>;
  created_at: string;
};

export type DeskResponse = {
  slug: string;
  market_found: boolean;
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
  market: { slug: string; title: string; status: string } | null;
  edge: DeskEdge | null;
  smart_money: SmartMoney | null;
  arb: DeskArb | null;
  signals: DeskSignal[];
  generated_at: string;
};

// ---------------------------------------------------------------------------
// View model (pure — unit-tested)
// ---------------------------------------------------------------------------

export type DeskEdgeView = {
  /** "62%" — model P(YES). */
  modelLabel: string;
  /** "+12.0 pts" vs best book price, or null when the local book is empty. */
  edgeLabel: string | null;
  edgeTone: "up" | "down" | "neutral";
  /** "conf 0.70" or null when the contract omits confidence. */
  confidenceLabel: string | null;
  sourceLabel: string;
};

export type DeskSmartMoneyView = {
  found: boolean;
  concentrationLabel: string;
  walletCountLabel: string;
  /** Most recent large flow, or null when none observed in the window. */
  lastFlow: {
    wallet: string;
    direction: string;
    outcome: string;
    sizeLabel: string;
    isBuy: boolean;
  } | null;
  /** Per-section backend error strings (honest partial degradation). */
  errors: string[];
};

export type DeskArbView = {
  counterpartSlug: string;
  counterpartTitle: string;
  confidenceLabel: string;
  spreadNote: string | null;
  stale: boolean;
};

export type DeskSignalView = {
  id: string;
  typeLabel: string;
  platform: string;
  createdAt: string;
  evidence: SignalEvidence | null;
};

export type DeskView = {
  found: boolean;
  slug: string;
  disclaimer: string;
  edge: DeskEdgeView | null;
  smartMoney: DeskSmartMoneyView;
  arb: DeskArbView | null;
  signals: DeskSignalView[];
  hasSignals: boolean;
};

const FALLBACK_DISCLAIMER =
  "Research desk aggregate — signal only; paper trading only, simulated funds, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function sizeCompact(value: number): string {
  const v = isFiniteNum(value) ? value : 0;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

function buildEdgeView(edge: DeskEdge | null): DeskEdgeView | null {
  if (!edge || !isFiniteNum(edge.predicted_prob)) return null;
  const vs = isFiniteNum(edge.edge_vs_book) ? edge.edge_vs_book : null;
  return {
    modelLabel: `${(edge.predicted_prob * 100).toFixed(0)}%`,
    edgeLabel:
      vs === null ? null : `${vs >= 0 ? "+" : ""}${(vs * 100).toFixed(1)} pts`,
    edgeTone: vs === null || Math.abs(vs) < 0.005 ? "neutral" : vs > 0 ? "up" : "down",
    confidenceLabel: isFiniteNum(edge.confidence)
      ? `conf ${edge.confidence.toFixed(2)}`
      : null,
    sourceLabel: edge.source || "prediction_log",
  };
}

function buildDeskSmartMoneyView(raw: SmartMoney | null): DeskSmartMoneyView {
  // Reuse the G07 view-model so /smart-money and the desk panel can never
  // disagree on formatting or error handling.
  const full: SmartMoneyView = buildSmartMoneyView(raw);
  if (!full.found) {
    return {
      found: false,
      concentrationLabel: "—",
      walletCountLabel: "0",
      lastFlow: null,
      errors: full.errors,
    };
  }
  const first = full.flows[0] ?? null;
  return {
    found: true,
    concentrationLabel: full.concentrationLabel,
    walletCountLabel: full.walletCountLabel,
    lastFlow: first
      ? {
          wallet: first.wallet,
          direction: first.direction,
          outcome: first.outcome,
          sizeLabel: first.sizeLabel,
          isBuy: first.isBuy,
        }
      : null,
    errors: full.errors,
  };
}

function buildArbView(slug: string, arb: DeskArb | null): DeskArbView | null {
  if (!arb) return null;
  const counterpartIsKs = arb.pm_slug === slug;
  // spread_bps is NOT part of the documented H01 arb shape (it lives on
  // /arb/opportunities). Render it only if the backend ever adds it; degrade
  // to the match reasons otherwise — never fabricate a spread.
  const spreadBps = (arb as { spread_bps?: unknown }).spread_bps;
  return {
    counterpartSlug: counterpartIsKs ? arb.ks_slug : arb.pm_slug,
    counterpartTitle: counterpartIsKs ? arb.ks_title : arb.pm_title,
    confidenceLabel: isFiniteNum(arb.confidence)
      ? `${(arb.confidence * 100).toFixed(0)}%`
      : "—",
    spreadNote: isFiniteNum(spreadBps)
      ? `${spreadBps.toFixed(0)} bps`
      : arb.reasons.length > 0
        ? `matched on ${arb.reasons.join(", ")}`
        : null,
    stale: arb.stale === true,
  };
}

function signalTypeLabel(signalType: string): string {
  return signalType.replace(/[:_]/g, " ");
}

/** Pure transform: raw H01 response → view model. Honest when market_found=false. */
export function buildDeskView(raw: DeskResponse | null): DeskView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw || !raw.market_found) {
    return {
      found: false,
      slug: raw?.slug ?? "",
      disclaimer,
      edge: null,
      smartMoney: buildDeskSmartMoneyView(raw?.smart_money ?? null),
      arb: null,
      signals: [],
      hasSignals: false,
    };
  }

  const signals: DeskSignalView[] = (Array.isArray(raw.signals) ? raw.signals : []).map(
    (s) => ({
      id: s.id,
      typeLabel: signalTypeLabel(s.signal_type),
      platform: s.platform,
      createdAt: s.created_at,
      evidence: extractSignalEvidence(s.signal_type, s.payload),
    }),
  );

  return {
    found: true,
    slug: raw.slug,
    disclaimer,
    edge: buildEdgeView(raw.edge),
    smartMoney: buildDeskSmartMoneyView(raw.smart_money),
    arb: buildArbView(raw.slug, raw.arb),
    signals,
    hasSignals: signals.length > 0,
  };
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

/** Fetch the desk aggregate. Returns null with no live API or on error. */
export async function fetchDesk(
  slug: string,
  opts?: { hours?: number; topN?: number; signalsLimit?: number; signal?: AbortSignal },
): Promise<DeskResponse | null> {
  const trimmed = slug.trim();
  if (!trimmed) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams({ slug: trimmed });
  if (opts?.hours) params.set("hours", String(opts.hours));
  if (opts?.topN) params.set("top_n", String(opts.topN));
  if (opts?.signalsLimit) params.set("signals_limit", String(opts.signalsLimit));
  try {
    const res = await fetch(`${apiUrl("/api/v1/desk", base)}?${params.toString()}`, {
      cache: "no-store",
      signal: opts?.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as DeskResponse;
  } catch {
    return null;
  }
}
