/**
 * Loop V85 (D-U2) — Usage summary typed client.
 *
 * Backend contract (U2):
 *   GET /api/v1/usage/summary?days=14 →
 *     {
 *       days:   [{date, sessions, skill_runs, scanner_runs, briefs}],
 *       totals: {sessions, skill_runs, scanner_runs, briefs}
 *     }
 *
 * The live API is attempted first (Bearer token like the other authed
 * clients); on any failure the caller gets a deterministic in-memory PAPER
 * mock so the /usage page works while the backend lands in parallel. Mirrors
 * `terminal-api.ts` / `skills-api.ts`: all fetch wiring lives here — UI
 * components never call `fetch`.
 *
 * PAPER_TRADING_ONLY — this is research-activity accounting only; there is
 * no order path and no real funds anywhere in these numbers.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/** Default lookback window (the ticket + backend contract both use 14 days). */
export const USAGE_DEFAULT_DAYS = 14;

/** Clamp applied to the `days` query param so a bad caller cannot DoS the API. */
export const USAGE_MAX_DAYS = 90;

// ---------------------------------------------------------------------------
// Types (U2 contract)
// ---------------------------------------------------------------------------

export type UsageDay = {
  /** ISO calendar day, `YYYY-MM-DD` (UTC on the backend). */
  date: string;
  sessions: number;
  skill_runs: number;
  scanner_runs: number;
  briefs: number;
};

export type UsageTotals = {
  sessions: number;
  skill_runs: number;
  scanner_runs: number;
  briefs: number;
};

export type UsageSummary = {
  /** One row per calendar day, oldest first. */
  days: UsageDay[];
  totals: UsageTotals;
};

export type ApiSource = "live" | "mock";

export type UsageResult =
  | { ok: true; summary: UsageSummary; source: ApiSource }
  | { ok: false; reason: "unavailable" };

// ---------------------------------------------------------------------------
// Payload guards + normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asCount(raw: unknown): number {
  const n = typeof raw === "number" ? raw : typeof raw === "string" ? Number(raw) : NaN;
  return Number.isFinite(n) && n >= 0 ? Math.round(n) : 0;
}

function normalizeDay(raw: unknown): UsageDay | null {
  const rec = asRecord(raw);
  if (typeof rec.date !== "string" || !rec.date) return null;
  return {
    date: rec.date,
    sessions: asCount(rec.sessions),
    skill_runs: asCount(rec.skill_runs ?? rec.skillRuns),
    scanner_runs: asCount(rec.scanner_runs ?? rec.scannerRuns),
    briefs: asCount(rec.briefs),
  };
}

/** Column sums over a day window — used for mock totals and as live backfill. */
export function computeUsageTotals(days: UsageDay[]): UsageTotals {
  const totals: UsageTotals = { sessions: 0, skill_runs: 0, scanner_runs: 0, briefs: 0 };
  for (const d of days) {
    totals.sessions += d.sessions;
    totals.skill_runs += d.skill_runs;
    totals.scanner_runs += d.scanner_runs;
    totals.briefs += d.briefs;
  }
  return totals;
}

function normalizeTotals(raw: unknown, days: UsageDay[]): UsageTotals {
  const rec = asRecord(raw);
  const keys: Array<keyof UsageTotals> = [
    "sessions",
    "skill_runs",
    "scanner_runs",
    "briefs",
  ];
  // Backend-provided totals win when they look numeric; otherwise recompute
  // from the day rows so the cards and the table can never disagree.
  const provided = keys.map((k) => rec[k]);
  if (provided.every((v) => typeof v === "number" && Number.isFinite(v))) {
    return {
      sessions: asCount(provided[0]),
      skill_runs: asCount(provided[1]),
      scanner_runs: asCount(provided[2]),
      briefs: asCount(provided[3]),
    };
  }
  return computeUsageTotals(days);
}

/** Normalize a raw summary payload; `null` when there is nothing usable. */
export function normalizeUsageSummary(raw: unknown): UsageSummary | null {
  const rec = asRecord(raw);
  const rawDays = Array.isArray(rec.days) ? rec.days : null;
  if (!rawDays) return null;
  const days = rawDays
    .map(normalizeDay)
    .filter((d): d is UsageDay => d !== null)
    .sort((a, b) => a.date.localeCompare(b.date));
  if (days.length === 0) return null;
  return { days, totals: normalizeTotals(rec.totals, days) };
}

// ---------------------------------------------------------------------------
// Mock store (deterministic; used whenever the live usage API is absent)
// ---------------------------------------------------------------------------

/** Fixed anchor so the mock window never drifts between renders / tests. */
const MOCK_ANCHOR_DATE = "2026-07-21";

/** Smooth deterministic wobble in [-1, 1] — no Math.random (stable tests). */
function wobble(seed: number): number {
  return Math.sin(seed * 1.7) * 0.5 + Math.sin(seed * 0.9 + 2.1) * 0.5;
}

function mockCount(seed: number, min: number, span: number): number {
  return min + Math.round(((wobble(seed) + 1) / 2) * span);
}

function isoDayOffset(anchor: string, offsetDays: number): string {
  const d = new Date(`${anchor}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

/** Deterministic paper activity for the last `days` calendar days. */
export function buildMockUsageDays(days: number): UsageDay[] {
  const out: UsageDay[] = [];
  for (let i = 0; i < days; i += 1) {
    out.push({
      date: isoDayOffset(MOCK_ANCHOR_DATE, i - (days - 1)),
      sessions: mockCount(i, 2, 7),
      skill_runs: mockCount(i + 31, 1, 5),
      scanner_runs: mockCount(i + 67, 0, 5),
      briefs: mockCount(i + 113, 0, 3),
    });
  }
  return out;
}

function buildMockSummary(days: number): UsageSummary {
  const mockDays = buildMockUsageDays(days);
  return { days: mockDays, totals: computeUsageTotals(mockDays) };
}

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the usage API)
// ---------------------------------------------------------------------------

type UsageFetch = typeof fetch;

let usageFetch: UsageFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setUsageFetch(fn: UsageFetch): void {
  usageFetch = fn;
}

async function liveBase(): Promise<string | null> {
  const base = (await ensureApiBase()) || undefined;
  return base && hasLiveApi(base) ? base : null;
}

async function tryLiveJson<T>(
  path: string,
  token: string | null,
  init?: RequestInit,
): Promise<T | null> {
  const base = await liveBase();
  if (!base) return null;
  try {
    const res = await usageFetch(apiUrl(path, base), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
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
 * Fetch the usage summary (live first, mock fallback). Never rejects — any
 * failure degrades to the deterministic paper mock so /usage stays verifiable
 * while the backend is built in parallel.
 */
export async function getUsageSummary(
  days: number = USAGE_DEFAULT_DAYS,
  token: string | null = null,
): Promise<{ summary: UsageSummary; source: ApiSource }> {
  const window = Math.min(Math.max(Math.round(days) || USAGE_DEFAULT_DAYS, 1), USAGE_MAX_DAYS);
  const live = await tryLiveJson<unknown>(
    `/api/v1/usage/summary?days=${window}`,
    token,
  );
  const normalized = live ? normalizeUsageSummary(live) : null;
  if (normalized) return { summary: normalized, source: "live" };
  return { summary: buildMockSummary(window), source: "mock" };
}
