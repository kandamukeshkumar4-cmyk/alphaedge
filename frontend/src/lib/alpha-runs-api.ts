/**
 * Alpha runs / latest signal / hypotheses typed client.
 *
 * Backend contract (loop97 `AlphaRunService`, `backend/app/api/v1/alpha.py`):
 *   GET /api/v1/alpha/runs ->
 *     {latest, runs: [{id, run_date, status, result, rejection_reasons, …}],
 *      paper_trading_only}
 *   GET /api/v1/alpha/latest-signal ->
 *     {run_date, signal: {label, status, weights, residual_alpha_t_stat, …},
 *      rejection_reasons, paper_trading_only}
 *     — or {signal: null, reason: "no_alpha_runs", paper_trading_only} when empty
 *   GET /api/v1/alpha/hypotheses ->
 *     {run_date, hypotheses: {proposed, verdicts, survivors, rejected, …},
 *      rejection_reasons, paper_trading_only}
 *
 * Live API first. On any failure / unparseable shape the caller gets an honest
 * empty payload with source "mock" — never fabricated seed rows. UI empty-states
 * already cover the zero-data case.
 *
 * PAPER_TRADING_ONLY — research output only; nothing here constructs orders.
 * A signal shows only when the residual alpha beats the closing line
 * out-of-sample (t-stat past the validator threshold).
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

// ---------------------------------------------------------------------------
// Types (UI view-model; mapped from the backend envelope)
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

function runDateToIso(runDate: string | null): string | null {
  if (!runDate) return null;
  // Backend sends YYYY-MM-DD; UI formatters parse via Date.parse.
  if (/^\d{4}-\d{2}-\d{2}$/.test(runDate)) return `${runDate}T00:00:00.000Z`;
  return runDate;
}

function formatRejectionEvidence(reasons: unknown): string {
  if (!Array.isArray(reasons) || reasons.length === 0) return "";
  const parts: string[] = [];
  for (const entry of reasons) {
    const rec = asRecord(entry);
    const factor =
      asStringOrNull(rec.factor) ??
      asStringOrNull(rec.hypothesis) ??
      asStringOrNull(rec.node);
    const reason = asStringOrNull(rec.reason);
    if (factor && reason) parts.push(`${factor}: ${reason}`);
    else if (reason) parts.push(reason);
  }
  return parts.join("; ");
}

function normalizeRun(raw: unknown, index: number): AlphaRun {
  const rec = asRecord(raw);
  const result = asRecord(rec.result);
  const decomp = asRecord(result.decomposition);
  const signal = asRecord(result.signal);
  const status = asStringOrNull(rec.status) ?? "unknown";
  const runDateIso = runDateToIso(asStringOrNull(rec.run_date));
  const residual =
    asFiniteNumber(decomp.residual_alpha) ??
    asFiniteNumber(rec.residual_alpha);
  const tStat =
    asFiniteNumber(decomp.residual_alpha_t_stat) ??
    asFiniteNumber(signal.residual_alpha_t_stat) ??
    asFiniteNumber(rec.t_stat);

  return {
    id: asStringOrNull(rec.id) ?? `run_${index + 1}`,
    started_at: asStringOrNull(rec.started_at) ?? runDateIso ?? "",
    finished_at: asStringOrNull(rec.finished_at) ?? runDateIso,
    status,
    residual_alpha: residual,
    t_stat: tStat,
    signal_emitted:
      rec.signal_emitted === true ||
      status === "genuine_edge" ||
      asStringOrNull(signal.status) === "genuine_edge",
  };
}

/** Parse `{latest, runs, paper_trading_only}` — the real prod envelope. */
function normalizeRuns(raw: unknown): AlphaRuns | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.runs)) return null;
  return {
    items: rec.runs.map((item, i) => normalizeRun(item, i)),
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

/**
 * Parse `{run_date, signal, rejection_reasons, paper_trading_only}` or the
 * empty `{signal: null, reason: "no_alpha_runs", …}` shape.
 */
function normalizeLatestSignal(raw: unknown): LatestSignal | null {
  const rec = asRecord(raw);
  // Require the prod discriminator (`signal` key) — never invent rows.
  if (!("signal" in rec)) return null;

  const signalRaw = rec.signal;
  const paper = rec.paper_trading_only !== false;
  const runDateIso = runDateToIso(asStringOrNull(rec.run_date));

  if (signalRaw === null || signalRaw === undefined) {
    return {
      emitted: false,
      residual_alpha: null,
      t_stat: null,
      evidence: asStringOrNull(rec.reason) ?? "",
      weights: null,
      created_at: runDateIso,
      paper_trading_only: paper,
    };
  }

  const signal = asRecord(signalRaw);
  const status = asStringOrNull(signal.status) ?? "no_signal";
  const emitted = status === "genuine_edge";
  const label = asStringOrNull(signal.label);
  const rejectionEvidence = formatRejectionEvidence(rec.rejection_reasons);
  let evidence = "";
  if (emitted) {
    evidence = label ?? "";
  } else if (rejectionEvidence) {
    evidence = rejectionEvidence;
  } else if (label) {
    evidence = label;
  }

  return {
    emitted,
    residual_alpha: asFiniteNumber(signal.residual_alpha),
    t_stat: asFiniteNumber(signal.residual_alpha_t_stat),
    evidence,
    weights: normalizeWeights(signal.weights),
    created_at: runDateIso,
    paper_trading_only: paper,
  };
}

function normalizeHypothesisFromProposed(
  proposed: unknown,
  verdict: Record<string, unknown> | undefined,
  rejected: Record<string, unknown> | undefined,
  index: number,
): Hypothesis {
  const rec = asRecord(proposed);
  const validated = verdict?.valid === true;
  return {
    name: asStringOrNull(rec.name) ?? `hypothesis_${index + 1}`,
    description: asStringOrNull(rec.description),
    predicted_direction: asStringOrNull(rec.predicted_direction),
    validated,
    reason: validated
      ? null
      : asStringOrNull(verdict?.reason) ?? asStringOrNull(rejected?.reason),
  };
}

/**
 * Parse `{run_date, hypotheses: {proposed, verdicts, …}, paper_trading_only}`.
 * Joins proposed tickets with verdict / rejected evidence into UI rows.
 */
function normalizeHypotheses(raw: unknown): Hypotheses | null {
  const rec = asRecord(raw);
  if (!("hypotheses" in rec)) return null;
  const hyp = asRecord(rec.hypotheses);
  const proposed = Array.isArray(hyp.proposed) ? hyp.proposed : [];
  const verdicts = Array.isArray(hyp.verdicts) ? hyp.verdicts : [];
  const rejected = Array.isArray(hyp.rejected) ? hyp.rejected : [];

  const verdictByName = new Map<string, Record<string, unknown>>();
  for (const entry of verdicts) {
    const vr = asRecord(entry);
    const name = asStringOrNull(vr.name);
    if (name) verdictByName.set(name, vr);
  }
  const rejectedByName = new Map<string, Record<string, unknown>>();
  for (const entry of rejected) {
    const rr = asRecord(entry);
    const name = asStringOrNull(rr.name);
    if (name) rejectedByName.set(name, rr);
  }

  let items: Hypothesis[];
  if (proposed.length > 0) {
    items = proposed.map((p, i) => {
      const name =
        asStringOrNull(asRecord(p).name) ?? `hypothesis_${i + 1}`;
      return normalizeHypothesisFromProposed(
        p,
        verdictByName.get(name),
        rejectedByName.get(name),
        i,
      );
    });
  } else if (verdicts.length > 0) {
    // No proposed tickets persisted — still surface validator evidence.
    items = verdicts.map((v, i) => {
      const vr = asRecord(v);
      const validated = vr.valid === true;
      return {
        name: asStringOrNull(vr.name) ?? `hypothesis_${i + 1}`,
        description: null,
        predicted_direction: null,
        validated,
        reason: validated ? null : asStringOrNull(vr.reason),
      };
    });
  } else {
    items = [];
  }

  return {
    items,
    paper_trading_only: rec.paper_trading_only !== false,
  };
}

function emptyRuns(): AlphaRuns {
  return { items: [], paper_trading_only: true };
}

function emptyLatestSignal(): LatestSignal {
  return {
    emitted: false,
    residual_alpha: null,
    t_stat: null,
    evidence: "",
    weights: null,
    created_at: null,
    paper_trading_only: true,
  };
}

function emptyHypotheses(): Hypotheses {
  return { items: [], paper_trading_only: true };
}

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
 * Run history for the daily alpha research tail. Live first; honest empty on
 * failure. Never rejects. Never fabricates seed rows.
 */
export async function getRuns(
  token: string | null = null,
): Promise<{ data: AlphaRuns; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/runs", token);
  const normalized = normalizeRuns(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: emptyRuns(), source: "mock" };
}

/**
 * Latest emitted (or withheld) signal with its evidence line. Live first;
 * honest empty on failure. Never rejects. Never fabricates seed rows.
 */
export async function getLatestSignal(
  token: string | null = null,
): Promise<{ data: LatestSignal; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/latest-signal", token);
  const normalized = normalizeLatestSignal(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: emptyLatestSignal(), source: "mock" };
}

/**
 * Idea-generator proposals with validation verdicts. Live first; honest empty
 * on failure. Never rejects. Never fabricates seed rows.
 */
export async function getHypotheses(
  token: string | null = null,
): Promise<{ data: Hypotheses; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/alpha/hypotheses", token);
  const normalized = normalizeHypotheses(live);
  if (normalized) return { data: normalized, source: "live" };
  return { data: emptyHypotheses(), source: "mock" };
}
