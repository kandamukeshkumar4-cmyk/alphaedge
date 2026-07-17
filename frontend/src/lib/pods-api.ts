import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * Loop V60 — pods command center API contracts (backend ships in parallel).
 *
 * READ-ONLY: these endpoints describe the paper-trading pod fleet. There is
 * no order path here — orders stay behind RiskService -> OrderIntent ->
 * OrderBookService. If an endpoint 404s (not yet deployed), callers get a
 * discriminated "not-deployed" result so the UI can render an honest state
 * instead of fabricated numbers.
 */

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

// ---------------------------------------------------------------------------
// Contract shapes (mirror the backend payloads exactly)
// ---------------------------------------------------------------------------

export type PodSummary = {
  id: string;
  name: string;
  status: string;
  bankroll: number;
  equity: number;
  pnl_24h: number;
  trades_count: number;
  last_decision_at: string | null;
};

export type PodEquityPoint = { t: string; equity: number };

export type PodsResponse = {
  pods: PodSummary[];
  equity_curves: Record<string, PodEquityPoint[]>;
};

export type HeartbeatDecision = {
  t: string;
  pod: string;
  market: string;
  rule: string;
  action: string;
  latency_ms: number;
};

export type HeartbeatDecisionsResponse = {
  decisions: HeartbeatDecision[];
};

export type MarketContextResponse = {
  whale_pressure: number;
  venue_gap: number;
  news_signal: number;
  price_trend: number;
  volume_pct: number;
  captured_at: string;
};

// ---------------------------------------------------------------------------
// Result type — 404 ("not yet deployed") is distinct from other failures.
// ---------------------------------------------------------------------------

export type PodsApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; reason: "not-deployed" | "unavailable" };

function notDeployed<T>(): PodsApiResult<T> {
  return { ok: false, reason: "not-deployed" };
}

function unavailable<T>(): PodsApiResult<T> {
  return { ok: false, reason: "unavailable" };
}

async function fetchContract<T>(
  path: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<PodsApiResult<T>> {
  const base =
    input?.apiBase !== undefined
      ? input.apiBase.trim().replace(/\/+$/, "")
      : (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return unavailable();

  const fetcher = input?.fetcher ?? fetch;
  try {
    const response = await fetcher(apiUrl(path, base), { cache: "no-store" });
    if (response.status === 404) return notDeployed();
    if (!response.ok) return unavailable();
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return unavailable();
  }
}

/** GET /api/v1/pods — pod fleet + per-pod equity curves. */
export async function fetchPods(input?: {
  apiBase?: string;
  fetcher?: Fetcher;
}): Promise<PodsApiResult<PodsResponse>> {
  return fetchContract<PodsResponse>("/api/v1/pods", input);
}

/** GET /api/v1/heartbeat/decisions — recent rule decisions across pods. */
export async function fetchHeartbeatDecisions(input?: {
  apiBase?: string;
  fetcher?: Fetcher;
  limit?: number;
}): Promise<PodsApiResult<HeartbeatDecisionsResponse>> {
  const limit = input?.limit;
  const path =
    limit && limit > 0
      ? `/api/v1/heartbeat/decisions?limit=${encodeURIComponent(String(limit))}`
      : "/api/v1/heartbeat/decisions";
  return fetchContract<HeartbeatDecisionsResponse>(path, input);
}

/** GET /api/v1/markets/{slug}/context — master context panel per market. */
export async function fetchMarketContext(
  slug: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<PodsApiResult<MarketContextResponse>> {
  const trimmed = slug.trim();
  if (!trimmed) return unavailable();
  return fetchContract<MarketContextResponse>(
    `/api/v1/markets/${encodeURIComponent(trimmed)}/context`,
    input,
  );
}

// ---------------------------------------------------------------------------
// Pure view helpers (unit-tested; components stay dumb)
// ---------------------------------------------------------------------------

export type PodStatusKind = "running" | "halted" | "flag-off" | "unknown";

/** Map a raw backend status onto the three chip states the design supports. */
export function normalizePodStatus(status: string | null | undefined): PodStatusKind {
  const value = (status ?? "").trim().toLowerCase();
  if (value === "running" || value === "active" || value === "live") return "running";
  if (value === "halted" || value === "paused" || value === "stopped") return "halted";
  if (value === "flag-off" || value === "flag_off" || value === "flagoff" || value === "off") {
    return "flag-off";
  }
  return "unknown";
}

export type DecisionActionTone = "buy" | "sell" | "neutral";

/**
 * Color a decision action with the existing trade tokens: buy/enter side is
 * the green (primary) token, sell/exit side is the red (danger) token, every
 * other action (skip/hold/no-trade) stays muted.
 */
export function decisionActionTone(action: string | null | undefined): DecisionActionTone {
  const value = (action ?? "").trim().toLowerCase();
  if (value.startsWith("buy") || value.startsWith("enter") || value.startsWith("long")) {
    return "buy";
  }
  if (value.startsWith("sell") || value.startsWith("exit") || value.startsWith("close")) {
    return "sell";
  }
  return "neutral";
}

/** Newest-first ordering for the decision terminal (defensive copy). */
export function sortDecisionsNewestFirst(
  decisions: HeartbeatDecision[],
): HeartbeatDecision[] {
  return [...decisions].sort((a, b) => {
    const at = Date.parse(a.t);
    const bt = Date.parse(b.t);
    const aMs = Number.isNaN(at) ? 0 : at;
    const bMs = Number.isNaN(bt) ? 0 : bt;
    return bMs - aMs;
  });
}

/** Stable identity for a decision row — used to blink rows that are new. */
export function decisionKey(decision: HeartbeatDecision): string {
  return `${decision.t}|${decision.pod}|${decision.market}|${decision.rule}|${decision.action}`;
}

/**
 * Keys in `decisions` that are not in `known` — the rows the terminal should
 * blink. The very first successful load passes `known = null` and marks
 * nothing as new (the whole list is "new" on first paint; blinking every row
 * would be noise).
 */
export function findNewDecisionKeys(
  known: ReadonlySet<string> | null,
  decisions: HeartbeatDecision[],
): Set<string> {
  if (known === null) return new Set();
  const fresh = new Set<string>();
  for (const decision of decisions) {
    const key = decisionKey(decision);
    if (!known.has(key)) fresh.add(key);
  }
  return fresh;
}

/**
 * Terminal timestamp for a decision row: HH:MM:SS (UTC, locale-independent so
 * SSR and client paint identical text). Unparseable input renders as "—".
 */
export function formatDecisionTime(iso: string): string {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "—";
  return new Date(ms).toISOString().slice(11, 19);
}

/** Clamp a contract number into [min, max]; non-finite input -> fallback. */
export function clampMetric(
  value: number | null | undefined,
  min: number,
  max: number,
  fallback = min,
): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

// ---------------------------------------------------------------------------
// U4 — market context panel view helpers (descriptive only, never advice)
// ---------------------------------------------------------------------------

export type WhalePressureTier = "quiet" | "building" | "heavy";

/**
 * Intensity tier for the whale-pressure gauge. whale_pressure is a 0..1 share;
 * the tier only describes how concentrated recent large-wallet flow is — it
 * says nothing about direction or what anyone should do about it.
 */
export function whalePressureTier(value: number | null | undefined): WhalePressureTier {
  const v = clampMetric(value, 0, 1);
  if (v >= 0.67) return "heavy";
  if (v >= 0.34) return "building";
  return "quiet";
}

/** Gauge fill percentage (0-100) for the whale-pressure bar; clamps outliers. */
export function whalePressurePct(value: number | null | undefined): number {
  return Math.round(clampMetric(value, 0, 1) * 100);
}

export type NewsSignalTone = "positive" | "neutral" | "negative";

/** Headline-tone bucket for the -1..1 news_signal score. */
export function newsSignalTone(value: number | null | undefined): NewsSignalTone {
  const v = clampMetric(value, -1, 1, 0);
  if (v > 0.2) return "positive";
  if (v < -0.2) return "negative";
  return "neutral";
}

/**
 * Signed venue gap in cents: 0.015 -> "+1.5¢", -0.02 -> "-2.0¢", 0 -> "0.0¢".
 * The sign is shown as-is (this market vs the reference venue); the panel
 * never interprets it as an opportunity.
 */
export function formatVenueGap(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const cents = value * 100;
  const sign = cents > 0 ? "+" : cents < 0 ? "-" : "";
  return `${sign}${Math.abs(cents).toFixed(1)}¢`;
}

/** Signed percent for price_trend: 0.06 -> "+6.0%", -0.025 -> "-2.5%". */
export function formatSignedPct(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : pct < 0 ? "-" : "";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}

/** Volume share of the market's typical pace: 0.81 -> "81%". */
export function formatVolumePct(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${Math.round(Math.max(0, value) * 100)}%`;
}
