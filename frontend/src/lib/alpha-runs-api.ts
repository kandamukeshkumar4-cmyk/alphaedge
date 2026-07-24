/**
 * Loop 102 AR1 — Alpha runs / latest signal / hypotheses typed client.
 *
 * Backend contract (loop102 alpha router, `backend/app/api/v1/alpha.py`):
 *   GET /api/v1/alpha/runs ->
 *     {items: [{id, started_at, finished_at, status, residual_alpha,
 *      t_stat, signal_emitted}]}
 *   GET /api/v1/alpha/latest-signal ->
 *     {emitted, residual_alpha, t_stat, evidence, weights?, created_at}
 *   GET /api/v1/alpha/hypotheses ->
 *     {items: [{name, description, predicted_direction, validated, reason}]}
 *
 * The live API is attempted first; on any failure the caller gets an
 * in-memory PAPER mock so the /alpha research view works while the backend
 * is absent. All fetch wiring lives in this one file — UI components never
 * call `fetch` themselves.
 *
 * PAPER_TRADING_ONLY — research output only; nothing here constructs orders.
 * A signal shows only when the residual alpha beats the closing line
 * out-of-sample (t-stat past the validator threshold).
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

// ---------------------------------------------------------------------------
// Types (backend contract)
// ---------------------------------------------------------------------------

export type AlphaRun = {
  id: string;
  /** ISO timestamp of when the daily research run started. */
  started_at: string;
  /** ISO timestamp of completion; null while the run is still in flight. */
  finished_at: string | null;
  /** Validator outcome code, e.g. `genuine_edge`, `no_signal`, `failed`. */
  status: string;
  /** OOS residual alpha of the combined research portfolio; null when none. */
  residual_alpha: number | null;
  /** Newey-West t-stat of the residual alpha; null when not computed. */
  t_stat: number | null;
  /** True only when the run emitted a signal that beat the closing line OOS. */
  signal_emitted: boolean;
};

export type AlphaRuns = {
  items: AlphaRun[];
  paper_trading_only: boolean;
};

export type LatestSignal = {
  /** True only when the latest run beat the closing line out-of-sample. */
  emitted: boolean;
  residual_alpha: number | null;
  t_stat: number | null;
  /** Human-readable evidence line — shown verbatim when no signal emitted. */
  evidence: string;
  /** Research weights per surviving factor; null when nothing survived. */
  weights: Record<string, number> | null;
  created_at: string | null;
  paper_trading_only: boolean;
};

export type Hypothesis = {
  name: string;
  description: string | null;
  /** Predicted direction the idea generator proposes, e.g. `yes` / `no`. */
  predicted_direction: string | null;
  /** True when the proposal survived OOS validation. */
  validated: boolean;
  /** Rejection reason when not validated; null for validated proposals. */
  reason: string | null;
};

export type Hypotheses = {
  items: Hypothesis[];
  paper_trading_only: boolean;
};

export type ApiSource = "live" | "mock";

// ---------------------------------------------------------------------------
// Human-readable run statuses (validator outcome codes → UI copy)
// ---------------------------------------------------------------------------

const RUN_STATUS_LABELS: Record<string, string> = {
  genuine_edge: "Edge confirmed",
  no_signal: "No signal",
  portfolio_not_constructed: "Portfolio not constructed",
  insufficient_data: "Insufficient data",
  failed: "Run failed",
  running: "Running",
  completed: "Completed",
};

/** Human read of a run status code (falls back to the raw code). */
export function alphaRunStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status.replaceAll("_", " ");
}

// ---------------------------------------------------------------------------
// Normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asFiniteNumber(value: unknown): number | null {
  const n =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : NaN;
  return Number.isFinite(n) ? n : null;
}

function asStringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function normalizeRun(raw: unknown, index: number): AlphaRun {
  const rec = asRecord(raw);
  return {
    id: asStringOrNull(rec.id) ?? `run_${index + 1}`,
    started_at: asStringOrNull(rec.started_at) ?? "",
    finished_at: asStringOrNull(rec.finished_at),
    status: asStringOrNull(rec.status) ?? "unknown",
    residual_alpha: asFiniteNumber(rec.residual_alpha),
    t_stat: asFiniteNumber(rec.t_stat),
    signal_emitted: rec.signal_emitted === true,
  };
}

function normalizeRuns(raw: unknown): AlphaRuns | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.items)) return null;
  return {
    items: rec.items.map((item, i) => normalizeRun(item, i)),
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

function normalizeWeights(raw: unknown): Record<string, number> | null {
  const rec = asRecord(raw);
  const weights: Record<string, number> = {};
  let count = 0;
  for (const [key, value] of Object.entries(rec)) {
    const n = asFiniteNumber(value);
    if (n === null) continue;
    weights[key] = n;
    count += 1;
  }
  return count > 0 ? weights : null;
}

function normalizeLatestSignal(raw: unknown): LatestSignal | null {
  const rec = asRecord(raw);
  if (typeof rec.emitted !== "boolean") return null;
  return {
    emitted: rec.emitted,
    residual_alpha: asFiniteNumber(rec.residual_alpha),
    t_stat: asFiniteNumber(rec.t_stat),
    evidence: asStringOrNull(rec.evidence) ?? "",
    weights: normalizeWeights(rec.weights),
    created_at: asStringOrNull(rec.created_at),
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

function normalizeHypothesis(raw: unknown, index: number): Hypothesis {
  const rec = asRecord(raw);
  const validated = rec.validated === true;
  return {
    name: asStringOrNull(rec.name) ?? `hypothesis_${index + 1}`,
    description: asStringOrNull(rec.description),
    predicted_direction: asStringOrNull(rec.predicted_direction),
    validated,
    reason: asStringOrNull(rec.reason),
  };
}

function normalizeHypotheses(raw: unknown): Hypotheses | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.items)) return null;
  return {
    items: rec.items.map((item, i) => normalizeHypothesis(item, i)),
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live alpha API is absent)
// ---------------------------------------------------------------------------

const MOCK_RUN_SEEDS: AlphaRun[] = [
  {
    id: "run-2026-07-24",
    started_at: "2026-07-24T06:00:00.000Z",
    finished_at: "2026-07-24T06:05:12.000Z",
    status: "no_signal",
    residual_alpha: 0.004,
    t_stat: 1.38,
    signal_emitted: false,
  },
  {
    id: "run-2026-07-23",
    started_at: "2026-07-23T06:00:00.000Z",
    finished_at: "2026-07-23T06:04:47.000Z",
    status: "genuine_edge",
    residual_alpha: 0.018,
    t_stat: 2.74,
    signal_emitted: true,
  },
  {
    id: "run-2026-07-22",
    started_at: "2026-07-22T06:00:00.000Z",
    finished_at: "2026-07-22T06:05:03.000Z",
    status: "no_signal",
    residual_alpha: 0.002,
    t_stat: 0.94,
    signal_emitted: false,
  },
  {
    id: "run-2026-07-21",
    started_at: "2026-07-21T06:00:00.000Z",
    finished_at: "2026-07-21T06:03:58.000Z",
    status: "portfolio_not_constructed",
    residual_alpha: null,
    t_stat: null,
    signal_emitted: false,
  },
  {
    id: "run-2026-07-20",
    started_at: "2026-07-20T06:00:00.000Z",
    finished_at: "2026-07-20T06:04:21.000Z",
    status: "no_signal",
    residual_alpha: 0.006,
    t_stat: 1.62,
    signal_emitted: false,
  },
];

function buildMockRuns(): AlphaRuns {
  return {
    items: MOCK_RUN_SEEDS.map((run) => ({ ...run })),
    paper_trading_only: true,
  };
}

function buildMockLatestSignal(): LatestSignal {
  // Mirrors the newest seeded run: no signal today, evidence on record.
  return {
    emitted: false,
    residual_alpha: 0.004,
    t_stat: 1.38,
    evidence:
      "Residual alpha t-stat 1.38 is below the 2.5 threshold — the combined research portfolio did not beat the closing line out-of-sample.",
    weights: null,
    created_at: "2026-07-24T06:05:12.000Z",
    paper_trading_only: true,
  };
}

const MOCK_HYPOTHESIS_SEEDS: Hypothesis[] = [
  {
    name: "back_to_back_fade",
    description:
      "Fade teams on the second night of a back-to-back when the closing price has moved against them.",
    predicted_direction: "no",
    validated: true,
    reason: null,
  },
  {
    name: "rest_advantage",
    description:
      "Teams with 2+ rest days against an equally rested opponent cover more often in the OOS window.",
    predicted_direction: "yes",
    validated: true,
    reason: null,
  },
  {
    name: "injury_overreaction",
    description:
      "Markets overreact to star-injury news within the first hour; mean-reversion edge on the opposite side.",
    predicted_direction: "yes",
    validated: false,
    reason: "Did not beat the closing line out-of-sample (t-stat 1.21).",
  },
  {
    name: "nationally_televised_overshoot",
    description:
      "Nationally televised games overshoot the projected total in the first half.",
    predicted_direction: "yes",
    validated: false,
    reason: "Too few uncorrelated event clusters to validate.",
  },
];

function buildMockHypotheses(): Hypotheses {
  return {
    items: MOCK_HYPOTHESIS_SEEDS.map((h) => ({ ...h })),
    paper_trading_only: true,
  };
}

/** Canonical seeded payloads — exported for fixtures and offline fallback. */
export const MOCK_ALPHA_RUNS: AlphaRuns = buildMockRuns();
export const MOCK_LATEST_SIGNAL: LatestSignal = buildMockLatestSignal();
export const MOCK_HYPOTHESES: Hypotheses = buildMockHypotheses();

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the alpha runs API)
// ---------------------------------------------------------------------------

type AlphaRunsFetch = typeof fetch;

let alphaRunsFetch: AlphaRunsFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setAlphaRunsFetch(fn: AlphaRunsFetch): void {
  alphaRunsFetch = fn;
}

/** Restore the default fetch layer (test hygiene). */
export function resetAlphaRunsFetch(): void {
  alphaRunsFetch = (...args) => fetch(...args);
}

async function tryLiveJson<T>(
  path: string,
  token: string | null,
): Promise<T | null> {
  const base = (await ensureApiBase()) || undefined;
  if (!base || !hasLiveApi(base)) return null;
  try {
    const res = await alphaRunsFetch(apiUrl(path, base), {
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Run history for the daily alpha research tail. Live first; paper mock
 * fallback. Never rejects.
 */
export async function getRuns(
  token: string | null = null,
): Promise<{ data: AlphaRuns; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/runs", token);
  const normalized = normalizeRuns(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: buildMockRuns(), source: "mock" };
}

/**
 * Latest emitted (or withheld) signal with its evidence line. Live first;
 * paper mock fallback. Never rejects.
 */
export async function getLatestSignal(
  token: string | null = null,
): Promise<{ data: LatestSignal; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/latest-signal", token);
  const normalized = normalizeLatestSignal(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: buildMockLatestSignal(), source: "mock" };
}

/**
 * Idea-generator proposals with validation verdicts. Live first; paper mock
 * fallback. Never rejects.
 */
export async function getHypotheses(
  token: string | null = null,
): Promise<{ data: Hypotheses; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/hypotheses", token);
  const normalized = normalizeHypotheses(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: buildMockHypotheses(), source: "mock" };
}
