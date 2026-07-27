/**
 * Loop V84 — Scanner Studio typed client.
 *
 * Backend contract (`backend/app/schemas/scanners.py`,
 * `backend/app/api/v1/scanners.py`):
 *   Scanner:   `{id, name, description, owner, spec, version, status,
 *               is_public, cooldown_minutes, created_at, updated_at,
 *               latest_run: ScannerRun | null}`
 *   Spec:      `{name, universe{categories, minimum_volume},
 *               schedule{timezone, market_hours_only, interval_minutes},
 *               steps[{type, window_days?}], delivery{email, in_app,
 *               cooldown_minutes}, limit, notes}`
 *   Run:       `{id, scanner_id, started_at, finished_at, status,
 *               checkpoint{node}|null, result{candidates, top_pick,
 *               counts}|null, error|null, repairs[{node,class,action}],
 *               repairs_count}` — candidates carry per-step `reads` keyed by
 *               step type + an `aligned` flag; `repairs` lists the
 *               deterministic self-heals the executor applied mid-run
 *               (backend loop87 — also mirrored on `result.repairs`).
 *
 * Endpoints: POST `/api/v1/scanners/compile` `{text}` -> `{spec, compiler,
 *               warnings}` (loop88 V2 — `compiler` is "deterministic" |
 *               "llm-assisted", `warnings` never blocks the compile);
 * POST `/api/v1/scanners/` (create, auth); GET `/api/v1/scanners/`;
 * GET `/api/v1/scanners/{id}` (with latest run); POST `/{id}/run`;
 * POST `/{id}/pause`; POST `/{id}/resume`; GET `/{id}/runs`.
 *
 * The live API is attempted first (Bearer token like the other authed
 * clients); on any failure the caller gets an in-memory PAPER mock so the UI
 * works while the backend is absent. All fetch wiring lives in this one
 * file — UI components never call `fetch` themselves. Mirrors the
 * live-first + mock-fallback pattern of `terminal-api.ts` (Loop V79).
 *
 * PAPER_TRADING_ONLY — scanners are research-only: they read markets and
 * never create paper orders (RiskService → OrderIntent → OrderBookService
 * is the sole order path and scanners never call it).
 */

import { apiUrl, ensureApiBase, formatApiDetail, hasLiveApi } from "@/lib/alphaedge-api";

// ---------------------------------------------------------------------------
// Types (backend contract)
// ---------------------------------------------------------------------------

export type ScannerStepType =
  | "WHALE_FLOW"
  | "PRICE_TREND"
  | "NEWS_SENTIMENT"
  | "MODEL_EDGE"
  | "DIRECTION_ALIGNMENT"
  | "CROSS_VENUE_DIVERGENCE"
  | "CLOSING_SOON";

export type ScannerStep = {
  type: ScannerStepType;
  window_days?: number;
};

export type ScannerUniverse = {
  categories: string[];
  minimum_volume: number;
};

export type ScannerSchedule = {
  timezone: string;
  market_hours_only: boolean;
  interval_minutes: number;
};

export type ScannerDelivery = {
  email: boolean;
  in_app: boolean;
  cooldown_minutes: number;
};

export type ScannerSpec = {
  name: string;
  universe: ScannerUniverse;
  schedule: ScannerSchedule;
  steps: ScannerStep[];
  delivery: ScannerDelivery;
  limit: number;
  notes: string[];
};

export type ScannerStatus = "draft" | "active" | "paused" | "failed";

export type ScannerRunStatus = "running" | "completed" | "empty" | "failed";

/** Step read direction — "up"/"down" per backend, null when inconclusive. */
export type StepDirection = "up" | "down" | null;

export type WhaleFlowRead = {
  pressure: number;
  event_count: number;
  net_notional: number;
  total_notional: number;
  direction: StepDirection;
  flow_score: number;
};

export type PriceTrendRead = {
  window_days: number;
  direction: StepDirection;
  change: number | null;
  candle_count: number;
};

export type NewsSentimentRead = {
  sentiment_score: number | null;
  direction: StepDirection;
  news: {
    headline: string;
    sentiment_score: number;
    sources_count: number;
  } | null;
  trend_available: boolean;
};

export type ModelEdgeRead = {
  model_prob: number | null;
  market_prob: number | null;
  edge: number | null;
  direction: StepDirection;
};

export type AlignmentRead = { aligned: boolean };

export type ScannerReads = {
  WHALE_FLOW?: WhaleFlowRead;
  PRICE_TREND?: PriceTrendRead;
  NEWS_SENTIMENT?: NewsSentimentRead;
  MODEL_EDGE?: ModelEdgeRead;
  DIRECTION_ALIGNMENT?: AlignmentRead;
};

export type ScannerCandidate = {
  market_slug: string;
  title: string;
  reads: ScannerReads;
  aligned: boolean;
};

export type ScannerRunCounts = {
  universe: number;
  candidates: number;
  aligned: number;
};

export type ScannerRunResult = {
  candidates: ScannerCandidate[];
  top_pick: ScannerCandidate | null;
  counts: ScannerRunCounts;
};

/**
 * Loop V88 (V1) — one deterministic self-heal the executor applied mid-run
 * (backend `scanner_heal_service`: 8-class classifier, bounded repairs).
 * `class` is the error class (`rate_limited`, `type_mismatch`, …); `action`
 * is the stable repair label (`sleep_retry`, `coerce_numeric`, …).
 */
export type ScannerRepair = {
  /** Pipeline node (step index) that failed and was healed. */
  node: number;
  class: string;
  action: string;
};

export type ScannerRun = {
  id: string;
  scanner_id: string;
  started_at: string;
  finished_at: string | null;
  status: ScannerRunStatus;
  checkpoint: { node: number } | null;
  result: ScannerRunResult | null;
  error: string | null;
  /** Wall-clock duration in ms (backend `_duration_ms`); null while running. */
  duration_ms: number | null;
  /** True for test-run snapshots (never trigger delivery / never publish). */
  is_test: boolean;
  /** Self-heal repairs applied on this run (loop87; empty when none). */
  repairs: ScannerRepair[];
};

export type Scanner = {
  id: string;
  name: string;
  description: string | null;
  owner: string | null;
  spec: ScannerSpec;
  version: number;
  status: ScannerStatus;
  is_public: boolean;
  cooldown_minutes: number;
  created_at: string;
  updated_at: string;
  latest_run: ScannerRun | null;
  /** Next scheduled run ISO (scheduler); null for draft / paused. */
  next_run_at: string | null;
  /** Last failure message across recent runs (dead-letter surface). */
  last_error: string | null;
};

/** One row of spec version history (GET /{id}/versions; mock-derived). */
export type ScannerVersion = {
  version: number;
  created_at: string;
  /** True when this is the scanner's current live version. */
  current: boolean;
};

export type ApiSource = "live" | "mock";

/** Loop V88 (V2) — which compiler path produced a spec preview. */
export type ScannerCompiler = "deterministic" | "llm-assisted";

// ---------------------------------------------------------------------------
// Payload guards + normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asDirection(value: unknown): StepDirection {
  return value === "up" || value === "down" ? value : null;
}

export const SCANNER_STEP_TYPES: readonly ScannerStepType[] = [
  "WHALE_FLOW",
  "PRICE_TREND",
  "NEWS_SENTIMENT",
  "MODEL_EDGE",
  "DIRECTION_ALIGNMENT",
  "CROSS_VENUE_DIVERGENCE",
  "CLOSING_SOON",
];

function normalizeStep(raw: unknown): ScannerStep | null {
  const rec = asRecord(raw);
  const type = String(rec.type ?? "").toUpperCase();
  if (!SCANNER_STEP_TYPES.includes(type as ScannerStepType)) return null;
  return {
    type: type as ScannerStepType,
    ...(typeof rec.window_days === "number" && Number.isFinite(rec.window_days)
      ? { window_days: rec.window_days }
      : {}),
  };
}

function normalizeSpec(raw: unknown): ScannerSpec {
  const rec = asRecord(raw);
  const universe = asRecord(rec.universe);
  const schedule = asRecord(rec.schedule);
  const delivery = asRecord(rec.delivery);
  return {
    name: typeof rec.name === "string" && rec.name.trim() ? rec.name : "Untitled scanner",
    universe: {
      categories: Array.isArray(universe.categories)
        ? universe.categories.map((c) => String(c))
        : [],
      minimum_volume: asNumber(universe.minimum_volume),
    },
    schedule: {
      timezone: typeof schedule.timezone === "string" ? schedule.timezone : "UTC",
      market_hours_only: schedule.market_hours_only === true,
      interval_minutes: asNumber(schedule.interval_minutes, 60) || 60,
    },
    steps: Array.isArray(rec.steps)
      ? rec.steps.map(normalizeStep).filter((s): s is ScannerStep => s !== null)
      : [],
    delivery: {
      email: delivery.email === true,
      in_app: delivery.in_app !== false,
      cooldown_minutes: asNumber(delivery.cooldown_minutes, 120),
    },
    limit: asNumber(rec.limit, 20) || 20,
    notes: Array.isArray(rec.notes) ? rec.notes.map((n) => String(n)) : [],
  };
}

function normalizeCandidate(raw: unknown): ScannerCandidate | null {
  const rec = asRecord(raw);
  if (typeof rec.market_slug !== "string") return null;
  const rawReads = asRecord(rec.reads);
  const reads: ScannerReads = {};
  const whale = asRecord(rawReads.WHALE_FLOW);
  if (rawReads.WHALE_FLOW !== undefined) {
    reads.WHALE_FLOW = {
      pressure: asNumber(whale.pressure),
      event_count: asNumber(whale.event_count),
      net_notional: asNumber(whale.net_notional),
      total_notional: asNumber(whale.total_notional),
      direction: asDirection(whale.direction),
      flow_score: asNumber(whale.flow_score),
    };
  }
  const trend = asRecord(rawReads.PRICE_TREND);
  if (rawReads.PRICE_TREND !== undefined) {
    reads.PRICE_TREND = {
      window_days: asNumber(trend.window_days, 7) || 7,
      direction: asDirection(trend.direction),
      change: typeof trend.change === "number" && Number.isFinite(trend.change) ? trend.change : null,
      candle_count: asNumber(trend.candle_count),
    };
  }
  const news = asRecord(rawReads.NEWS_SENTIMENT);
  if (rawReads.NEWS_SENTIMENT !== undefined) {
    const newsItem = asRecord(news.news);
    reads.NEWS_SENTIMENT = {
      sentiment_score:
        typeof news.sentiment_score === "number" && Number.isFinite(news.sentiment_score)
          ? news.sentiment_score
          : null,
      direction: asDirection(news.direction),
      news:
        typeof newsItem.headline === "string"
          ? {
              headline: newsItem.headline,
              sentiment_score: asNumber(newsItem.sentiment_score),
              sources_count: asNumber(newsItem.sources_count),
            }
          : null,
      trend_available: news.trend_available === true,
    };
  }
  const model = asRecord(rawReads.MODEL_EDGE);
  if (rawReads.MODEL_EDGE !== undefined) {
    reads.MODEL_EDGE = {
      model_prob:
        typeof model.model_prob === "number" && Number.isFinite(model.model_prob)
          ? model.model_prob
          : null,
      market_prob:
        typeof model.market_prob === "number" && Number.isFinite(model.market_prob)
          ? model.market_prob
          : null,
      edge: typeof model.edge === "number" && Number.isFinite(model.edge) ? model.edge : null,
      direction: asDirection(model.direction),
    };
  }
  const alignment = asRecord(rawReads.DIRECTION_ALIGNMENT);
  if (rawReads.DIRECTION_ALIGNMENT !== undefined) {
    reads.DIRECTION_ALIGNMENT = { aligned: alignment.aligned === true };
  }
  return {
    market_slug: rec.market_slug,
    title: typeof rec.title === "string" ? rec.title : rec.market_slug,
    reads,
    aligned: rec.aligned === true,
  };
}

function normalizeRunResult(raw: unknown): ScannerRunResult | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.candidates)) return null;
  const candidates = rec.candidates
    .map(normalizeCandidate)
    .filter((c): c is ScannerCandidate => c !== null);
  const counts = asRecord(rec.counts);
  return {
    candidates,
    top_pick: normalizeCandidate(rec.top_pick),
    counts: {
      universe: asNumber(counts.universe, candidates.length),
      candidates: asNumber(counts.candidates, candidates.length),
      aligned: asNumber(counts.aligned, candidates.filter((c) => c.aligned).length),
    },
  };
}

/** Loop V88 (V1) — repairs list from the API, tolerant of junk entries. */
function normalizeRepairs(raw: unknown): ScannerRepair[] {
  if (!Array.isArray(raw)) return [];
  const repairs: ScannerRepair[] = [];
  for (const item of raw) {
    const rec = asRecord(item);
    if (typeof rec.class !== "string" || typeof rec.action !== "string") continue;
    repairs.push({ node: asNumber(rec.node), class: rec.class, action: rec.action });
  }
  return repairs;
}

export function normalizeScannerRun(raw: unknown): ScannerRun | null {
  const rec = asRecord(raw);
  if (typeof rec.id !== "string") return null;
  const status = String(rec.status ?? "");
  const runStatus: ScannerRunStatus =
    status === "running" || status === "completed" || status === "empty" || status === "failed"
      ? status
      : "running";
  const checkpoint = asRecord(rec.checkpoint);
  const finishedAt = typeof rec.finished_at === "string" ? rec.finished_at : null;
  const startedAt = typeof rec.started_at === "string" ? rec.started_at : new Date(0).toISOString();
  // Prefer the backend's duration_ms; fall back to computing it from timestamps.
  const durationMs =
    typeof rec.duration_ms === "number" && Number.isFinite(rec.duration_ms)
      ? rec.duration_ms
      : finishedAt
        ? (() => {
            const ms = Date.parse(finishedAt) - Date.parse(startedAt);
            return Number.isFinite(ms) && ms >= 0 ? ms : null;
          })()
        : null;
  // Loop V88 (V1): the API lifts repairs to the run row (`repairs` +
  // `repairs_count`); older payloads only carry `result.repairs` — accept both.
  const repairs = normalizeRepairs(rec.repairs ?? asRecord(rec.result).repairs);
  return {
    id: rec.id,
    scanner_id: typeof rec.scanner_id === "string" ? rec.scanner_id : "",
    started_at: startedAt,
    finished_at: finishedAt,
    status: runStatus,
    checkpoint:
      typeof checkpoint.node === "number" && Number.isFinite(checkpoint.node)
        ? { node: checkpoint.node }
        : null,
    result: rec.result !== null && rec.result !== undefined ? normalizeRunResult(rec.result) : null,
    error: typeof rec.error === "string" ? rec.error : null,
    duration_ms: durationMs,
    is_test: rec.is_test === true,
    repairs,
  };
}

export function normalizeScanner(raw: unknown): Scanner | null {
  const rec = asRecord(raw);
  if (typeof rec.id !== "string") return null;
  const status = String(rec.status ?? "");
  const scannerStatus: ScannerStatus =
    status === "draft" || status === "active" || status === "paused" || status === "failed"
      ? status
      : "draft";
  return {
    id: rec.id,
    name: typeof rec.name === "string" && rec.name.trim() ? rec.name : "Untitled scanner",
    description: typeof rec.description === "string" ? rec.description : null,
    owner: typeof rec.owner === "string" ? rec.owner : null,
    spec: normalizeSpec(rec.spec),
    version: asNumber(rec.version, 1) || 1,
    status: scannerStatus,
    is_public: rec.is_public === true,
    cooldown_minutes: asNumber(rec.cooldown_minutes, 120),
    created_at: typeof rec.created_at === "string" ? rec.created_at : new Date(0).toISOString(),
    updated_at: typeof rec.updated_at === "string" ? rec.updated_at : new Date(0).toISOString(),
    latest_run: rec.latest_run ? normalizeScannerRun(rec.latest_run) : null,
    next_run_at: typeof rec.next_run_at === "string" ? rec.next_run_at : null,
    last_error: typeof rec.last_error === "string" && rec.last_error ? rec.last_error : null,
  };
}

// ---------------------------------------------------------------------------
// Derived helpers (pure) — UI formatting without components doing the math
// ---------------------------------------------------------------------------

/** "every 15 min" / "every 2 h" / "daily" — the schedule line on cards. */
export function scheduleLabel(spec: ScannerSpec): string {
  const minutes = spec.schedule.interval_minutes;
  if (minutes >= 1440) return "daily";
  if (minutes >= 60 && minutes % 60 === 0) {
    const hours = minutes / 60;
    return `every ${hours} h`;
  }
  return `every ${Math.max(1, minutes)} min`;
}

/** One-line label for a spec step, e.g. "Price trend · 7d window". */
export function stepLabel(step: ScannerStep): string {
  switch (step.type) {
    case "WHALE_FLOW":
      return "Whale flow";
    case "PRICE_TREND":
      return `Price trend · ${step.window_days ?? 7}d`;
    case "NEWS_SENTIMENT":
      return "News sentiment";
    case "MODEL_EDGE":
      return "Model vs market";
    case "DIRECTION_ALIGNMENT":
      return "Direction alignment";
    case "CROSS_VENUE_DIVERGENCE":
      return "Cross-Venue Divergence";
    case "CLOSING_SOON":
      return "Closing Soon";
  }
}

/** Run wall-clock duration in ms, or null while running/unknown. */
export function runDurationMs(run: ScannerRun): number | null {
  if (!run.finished_at) return null;
  const ms = Date.parse(run.finished_at) - Date.parse(run.started_at);
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

/** Compact duration label: "1.4s" / "820ms" / "—" while running. */
export function runDurationLabel(run: ScannerRun): string {
  const ms = runDurationMs(run);
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

/** Loop V88 (V1) — how many self-heal repairs the executor applied on a run. */
export function runRepairsCount(run: ScannerRun): number {
  return run.repairs.length;
}

/** "2m ago" style relative label for last-run lines (fixed `now` for tests). */
export function relativeTimeLabel(iso: string, nowMs: number = Date.now()): string {
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return "—";
  const delta = Math.max(0, nowMs - then);
  const minutes = Math.floor(delta / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Does the candidate's reads map carry a read for this step type? */
export function candidateHasRead(cand: ScannerCandidate, type: ScannerStepType): boolean {
  // The loop109 step types carry no read shape on ScannerReads yet — widen
  // the index so they resolve to `undefined` (absent) instead of a type error.
  return (cand.reads as Partial<Record<ScannerStepType, unknown>>)[type] !== undefined;
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live scanner API is absent)
// ---------------------------------------------------------------------------

const MOCK_NOW = "2026-07-21T15:00:00.000Z";

type MockMarket = { slug: string; title: string; category: string };

const MOCK_UNIVERSE: MockMarket[] = [
  { slug: "nba-2025-01-15-lal-bos", title: "Lakers vs Celtics — Jan 15", category: "nba" },
  { slug: "nba-2025-01-16-gsw-den", title: "Warriors vs Nuggets — Jan 16", category: "nba" },
  { slug: "nba-2025-01-16-mil-mia", title: "Bucks vs Heat — Jan 16", category: "nba" },
  { slug: "election-2026-senate-oh", title: "Ohio Senate 2026 winner", category: "election" },
  { slug: "crypto-btc-150k-2026", title: "BTC above $150k in 2026?", category: "crypto" },
];

function mockDirection(seed: number): StepDirection {
  return seed % 3 === 2 ? null : seed % 2 === 0 ? "up" : "down";
}

/**
 * Deterministic per-step read for a (step, market-index) pair — same shape as
 * the backend executor emits, no randomness so UI tests stay stable.
 */
function mockRead(step: ScannerStep, marketIndex: number): ScannerReads {
  switch (step.type) {
    case "WHALE_FLOW":
      return {
        WHALE_FLOW: {
          pressure: Number(((marketIndex % 2 === 0 ? 1 : -1) * (0.08 + marketIndex * 0.03)).toFixed(3)),
          event_count: 4 + marketIndex * 2,
          net_notional: 8_500 + marketIndex * 3_100,
          total_notional: 21_000 + marketIndex * 4_500,
          direction: mockDirection(marketIndex),
          flow_score: 9_300 + marketIndex * 2_800,
        },
      };
    case "PRICE_TREND": {
      const dir = mockDirection(marketIndex + 1);
      return {
        PRICE_TREND: {
          window_days: step.window_days ?? 7,
          direction: dir,
          change: dir === null ? null : Number((dir === "up" ? 0.018 : -0.014).toFixed(4)),
          candle_count: 24 * (step.window_days ?? 7),
        },
      };
    }
    case "NEWS_SENTIMENT":
      return {
        NEWS_SENTIMENT: {
          sentiment_score: Number(((marketIndex % 2 === 0 ? 1 : -1) * (0.12 + marketIndex * 0.02)).toFixed(3)),
          direction: mockDirection(marketIndex),
          news: {
            headline: `Desk read: ${MOCK_UNIVERSE[marketIndex % MOCK_UNIVERSE.length]?.title ?? "market"} coverage leans ${marketIndex % 2 === 0 ? "bullish" : "cautious"}`,
            sentiment_score: Number(((marketIndex % 2 === 0 ? 1 : -1) * 0.1).toFixed(3)),
            sources_count: 3 + marketIndex,
          },
          trend_available: true,
        },
      };
    case "MODEL_EDGE": {
      const marketProb = 0.48 + marketIndex * 0.02;
      const modelProb = marketProb + (marketIndex % 2 === 0 ? 0.05 : -0.02);
      const edge = Number((modelProb - marketProb).toFixed(4));
      return {
        MODEL_EDGE: {
          model_prob: Number(modelProb.toFixed(3)),
          market_prob: Number(marketProb.toFixed(3)),
          edge,
          direction: edge > 0.01 ? "up" : edge < -0.01 ? "down" : null,
        },
      };
    }
    case "DIRECTION_ALIGNMENT":
      return { DIRECTION_ALIGNMENT: { aligned: marketIndex % 2 === 0 } };
    case "CROSS_VENUE_DIVERGENCE":
      // loop109 step types carry no mock read shape yet — empty reads.
      return {};
    case "CLOSING_SOON":
      return {};
  }
}

function candidateDirections(reads: ScannerReads): StepDirection[] {
  const dirs: StepDirection[] = [
    reads.WHALE_FLOW?.direction ?? null,
    reads.PRICE_TREND?.direction ?? null,
    reads.NEWS_SENTIMENT?.direction ?? null,
    reads.MODEL_EDGE?.direction ?? null,
  ];
  return dirs.filter((d): d is "up" | "down" => d !== null);
}

function isCandidateAligned(reads: ScannerReads): boolean {
  const dirs = candidateDirections(reads);
  return dirs.length > 0 && new Set(dirs).size === 1;
}

/** Execute a spec over the mock universe — mirrors the backend executor. */
function mockExecute(
  spec: ScannerSpec,
  runId: string,
  startedAt: string,
  repairs: ScannerRepair[] = [],
): ScannerRun {
  const limit = Math.max(1, spec.limit || 20);
  const categories = spec.universe.categories.map((c) => c.toLowerCase());
  const universe = MOCK_UNIVERSE.filter(
    (m) => categories.length === 0 || categories.includes(m.category),
  ).slice(0, limit);

  if (universe.length === 0) {
    return {
      id: runId,
      scanner_id: "",
      started_at: startedAt,
      finished_at: startedAt,
      status: "empty",
      checkpoint: null,
      result: { candidates: [], top_pick: null, counts: { universe: 0, candidates: 0, aligned: 0 } },
      error: null,
      duration_ms: 0,
      is_test: false,
      repairs: [],
    };
  }

  let candidates: ScannerCandidate[] = universe.map((m) => ({
    market_slug: m.slug,
    title: m.title,
    reads: {},
    aligned: false,
  }));

  const alignPresent = spec.steps.some((s) => s.type === "DIRECTION_ALIGNMENT");
  for (const step of spec.steps) {
    candidates = candidates.map((cand, i) => ({
      ...cand,
      reads: { ...cand.reads, ...mockRead(step, i) },
    }));
    if (step.type === "DIRECTION_ALIGNMENT") {
      // Mirror backend: drop candidates whose signal directions conflict.
      candidates = candidates
        .map((cand) => {
          const aligned = isCandidateAligned(cand.reads);
          return {
            ...cand,
            aligned,
            reads: { ...cand.reads, DIRECTION_ALIGNMENT: { aligned } },
          };
        })
        .filter((cand) => {
          const dirs = candidateDirections(cand.reads);
          return !(dirs.length > 0 && !cand.aligned);
        });
    }
  }

  candidates = candidates.map((cand) =>
    alignPresent ? cand : { ...cand, aligned: isCandidateAligned(cand.reads) },
  );
  const aligned = candidates.filter((c) => c.aligned);
  const started = Date.parse(startedAt);
  const finishedAt = new Date(started + 4200).toISOString();
  return {
    id: runId,
    scanner_id: "",
    started_at: startedAt,
    finished_at: finishedAt,
    status: "completed",
    checkpoint: { node: Math.max(0, spec.steps.length - 1) },
    result: {
      candidates,
      top_pick: aligned[0] ?? null,
      counts: { universe: universe.length, candidates: candidates.length, aligned: aligned.length },
    },
    error: null,
    duration_ms: 4200,
    is_test: false,
    repairs,
  };
}

const MOCK_WHALE_SPEC: ScannerSpec = {
  name: "NBA whale + trend confluence",
  universe: { categories: ["nba"], minimum_volume: 50_000 },
  schedule: { timezone: "UTC", market_hours_only: false, interval_minutes: 15 },
  steps: [
    { type: "WHALE_FLOW" },
    { type: "PRICE_TREND", window_days: 7 },
    { type: "NEWS_SENTIMENT" },
    { type: "MODEL_EDGE" },
    { type: "DIRECTION_ALIGNMENT" },
  ],
  delivery: { email: false, in_app: true, cooldown_minutes: 120 },
  limit: 20,
  notes: [],
};

const MOCK_DAILY_SPEC: ScannerSpec = {
  name: "Election sentiment daily digest",
  universe: { categories: ["election"], minimum_volume: 10_000 },
  schedule: { timezone: "UTC", market_hours_only: false, interval_minutes: 1440 },
  steps: [{ type: "NEWS_SENTIMENT" }, { type: "MODEL_EDGE" }],
  delivery: { email: false, in_app: true, cooldown_minutes: 240 },
  limit: 10,
  notes: [],
};

const MOCK_DRAFT_SPEC: ScannerSpec = {
  name: "Crypto whale watcher",
  universe: { categories: ["crypto"], minimum_volume: 25_000 },
  schedule: { timezone: "UTC", market_hours_only: false, interval_minutes: 60 },
  steps: [{ type: "WHALE_FLOW" }, { type: "PRICE_TREND", window_days: 3 }],
  delivery: { email: false, in_app: true, cooldown_minutes: 120 },
  limit: 20,
  notes: [],
};

function makeMockRun(
  scannerId: string,
  spec: ScannerSpec,
  id: string,
  startedAt: string,
  repairs: ScannerRepair[] = [],
): ScannerRun {
  return { ...mockExecute(spec, id, startedAt, repairs), scanner_id: scannerId };
}

function seedMockStore(): { scanners: Scanner[]; runs: Record<string, ScannerRun[]> } {
  // Loop V88 (V1): the whale scanner's seeded runs carry self-heal repairs
  // (deterministic, mirroring backend loop87 vocabulary) so the heal chip +
  // ledger render without a live backend.
  const whaleRuns = [
    makeMockRun("scn-mock-whale", MOCK_WHALE_SPEC, "run-mock-whale-2", "2026-07-21T14:45:00.000Z", [
      { node: 1, class: "rate_limited", action: "sleep_retry" },
      { node: 3, class: "type_mismatch", action: "coerce_numeric" },
    ]),
    makeMockRun("scn-mock-whale", MOCK_WHALE_SPEC, "run-mock-whale-1", "2026-07-21T14:30:00.000Z", [
      { node: 0, class: "provider_transient", action: "retry_once" },
    ]),
  ];
  const dailyRuns = [
    makeMockRun("scn-mock-daily", MOCK_DAILY_SPEC, "run-mock-daily-1", "2026-07-21T06:00:00.000Z"),
  ];
  const scanners: Scanner[] = [
    {
      id: "scn-mock-whale",
      name: MOCK_WHALE_SPEC.name,
      description: "Whale flow, price trend, news and model agreement on NBA markets.",
      owner: "mock-user",
      spec: MOCK_WHALE_SPEC,
      version: 3,
      status: "active",
      is_public: true,
      cooldown_minutes: 120,
      created_at: "2026-07-18T12:00:00.000Z",
      updated_at: MOCK_NOW,
      latest_run: whaleRuns[0] ?? null,
      next_run_at: "2026-07-21T15:15:00.000Z",
      last_error: null,
    },
    {
      id: "scn-mock-daily",
      name: MOCK_DAILY_SPEC.name,
      description: "Once-a-day sentiment + model read on election markets.",
      owner: "mock-user",
      spec: MOCK_DAILY_SPEC,
      version: 2,
      status: "paused",
      is_public: true,
      cooldown_minutes: 240,
      created_at: "2026-07-19T09:00:00.000Z",
      updated_at: "2026-07-21T07:00:00.000Z",
      latest_run: dailyRuns[0] ?? null,
      next_run_at: null,
      last_error: null,
    },
    {
      id: "scn-mock-draft",
      name: MOCK_DRAFT_SPEC.name,
      description: null,
      owner: "mock-user",
      spec: MOCK_DRAFT_SPEC,
      version: 1,
      status: "draft",
      is_public: false,
      cooldown_minutes: 120,
      created_at: MOCK_NOW,
      updated_at: MOCK_NOW,
      latest_run: null,
      next_run_at: null,
      last_error: null,
    },
  ];
  return {
    scanners,
    runs: {
      "scn-mock-whale": whaleRuns,
      "scn-mock-daily": dailyRuns,
      "scn-mock-draft": [],
    },
  };
}

let mockStore = seedMockStore();
let mockCounter = 0;

function nextMockId(prefix: string): string {
  mockCounter += 1;
  return `${prefix}-local-${mockCounter.toString(36)}`;
}

export function resetScannersMockStore(): void {
  mockStore = seedMockStore();
  mockCounter = 0;
}

/** Mock-store read — used by community-api fork parity (no live backend). */
export function findMockScanner(id: string): Scanner | null {
  return mockStore.scanners.find((s) => s.id === id) ?? null;
}

/** Mock-store write — a forked scanner appears in the studio mock. */
export function insertMockScanner(scanner: Scanner): void {
  mockStore = {
    scanners: [scanner, ...mockStore.scanners.filter((s) => s.id !== scanner.id)],
    runs: { ...mockStore.runs, [scanner.id]: [] },
  };
}

/**
 * Mock NL→spec compile mirroring the backend's deterministic keyword parser
 * (`scanner_compiler_service.py`) — same signal keywords, interval phrases,
 * categories, minimum-volume and top-N parsing; residuals land in `notes`.
 */
export function compileSpecLocal(text: string): ScannerSpec {
  const raw = (text || "").trim();
  const lower = raw.toLowerCase();
  const spec: ScannerSpec = {
    name: "Untitled scanner",
    universe: { categories: [], minimum_volume: 0 },
    schedule: { timezone: "UTC", market_hours_only: false, interval_minutes: 60 },
    steps: [],
    delivery: { email: false, in_app: true, cooldown_minutes: 120 },
    limit: 20,
    notes: [],
  };
  if (!raw) {
    spec.notes = ["(empty)"];
    return spec;
  }
  spec.name = (raw.split(/[.!?\n]/)[0] ?? "").trim().slice(0, 80) || "Untitled scanner";

  const steps: ScannerStep[] = [];
  if (/\bwhale\b|\bflow\b/.test(lower)) steps.push({ type: "WHALE_FLOW" });
  if (/\btrend\b|\bmomentum\b|\bprice\b/.test(lower)) {
    const win = lower.match(/(\d+)\s*days?/);
    steps.push({ type: "PRICE_TREND", ...(win ? { window_days: Number(win[1]) } : { window_days: 7 }) });
  }
  if (/\bnews\b|\bsentiment\b/.test(lower)) steps.push({ type: "NEWS_SENTIMENT" });
  if (/\bmodel\b|\bedge\b/.test(lower)) steps.push({ type: "MODEL_EDGE" });
  const signalCount = steps.length;
  if (signalCount >= 2) steps.push({ type: "DIRECTION_ALIGNMENT" });
  spec.steps = steps;

  spec.universe.categories = (["nba", "sports", "election", "crypto"] as const).filter((cat) =>
    new RegExp(`\\b${cat}\\b`).test(lower),
  );
  const vol = lower.match(/volume\s+above\s+(\d[\d,]*)/) ?? lower.match(/min(?:imum)?\s+volume(?:\s+of)?\s+(\d[\d,]*)/);
  if (vol) spec.universe.minimum_volume = Number(vol[1].replace(/,/g, ""));

  if (/\bdaily\b/.test(lower)) {
    spec.schedule.interval_minutes = 1440;
  } else {
    const min = lower.match(/every\s+(\d+)\s*minutes?/);
    const hr = lower.match(/every\s+(\d+)\s*hours?/);
    if (min) spec.schedule.interval_minutes = Number(min[1]);
    else if (hr) spec.schedule.interval_minutes = Number(hr[1]) * 60;
  }
  const top = lower.match(/\btop\s+(\d+)\b/);
  if (top) spec.limit = Number(top[1]);

  const stop = new Set([
    "a", "an", "the", "and", "or", "with", "for", "of", "to", "in", "on", "at",
    "when", "show", "shows", "scan", "scanner", "alert", "me", "markets",
    "market", "above", "min", "minimum", "volume", "every", "minutes",
    "minute", "hours", "hour", "daily", "top", "day", "days", "window",
  ]);
  const known = new Set([
    "whale", "flow", "trend", "momentum", "price", "news", "sentiment",
    "model", "edge", "nba", "sports", "election", "crypto",
  ]);
  for (const tok of lower.match(/[a-z0-9]+(?:'[a-z]+)?/g) ?? []) {
    if (/^\d+$/.test(tok) || stop.has(tok) || known.has(tok)) continue;
    if (!spec.notes.includes(tok)) spec.notes.push(tok);
  }
  return spec;
}

const SIGNAL_STEP_TYPES: ReadonlySet<ScannerStepType> = new Set([
  "WHALE_FLOW",
  "PRICE_TREND",
  "NEWS_SENTIMENT",
  "MODEL_EDGE",
]);

/**
 * Loop V88 (V2) — mock parity for the backend's deterministic post-compile
 * warnings (`scanner_compiler_service.validate_spec`). Same rules, same
 * strings; warnings never block the compile.
 */
export function specWarningsLocal(spec: ScannerSpec): string[] {
  const warnings: string[] = [];
  if (spec.universe.categories.length === 0) warnings.push("empty universe");
  const interval = spec.schedule.interval_minutes;
  if (interval < 15 && spec.steps.length > 3) {
    warnings.push("spend warning: interval under 15 minutes with more than 3 steps");
  }
  if (!spec.steps.some((s) => SIGNAL_STEP_TYPES.has(s.type))) {
    warnings.push("no signal steps");
  }
  if (spec.delivery.cooldown_minutes < interval) {
    warnings.push("cooldown less than interval");
  }
  return warnings;
}

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the scanner API)
// ---------------------------------------------------------------------------

type ScannersFetch = typeof fetch;

let scannersFetch: ScannersFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setScannersFetch(fn: ScannersFetch): void {
  scannersFetch = fn;
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
    const res = await scannersFetch(apiUrl(path, base), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
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

function asList(live: unknown): unknown[] | null {
  if (Array.isArray(live)) return live;
  const rec = asRecord(live);
  if (Array.isArray(rec.items)) return rec.items;
  if (Array.isArray(rec.scanners)) return rec.scanners;
  return null;
}

// ---------------------------------------------------------------------------
// Endpoints — live first, mock fallback. None of these reject.
// ---------------------------------------------------------------------------

export type CompileScannerResult = {
  status: "ready" | "needs_clarification";
  draft_id: string | null;
  spec: ScannerSpec;
  spec_partial: ScannerSpec | null;
  questions: ClarifyQuestion[];
  /** Loop V88 (V2) — which compiler path produced the spec. */
  compiler: ScannerCompiler;
  /** Loop V88 (V2) — deterministic post-compile warnings (never blocking). */
  warnings: string[];
  source: ApiSource;
};

export type ClarifyQuestionKind =
  | "schedule"
  | "threshold"
  | "universe"
  | "delivery"
  | "other";

export type ClarifyQuestion = {
  id: string;
  question: string;
  kind: ClarifyQuestionKind;
  suggestions: string[];
};

export type CompileAnswer = {
  question_id: string;
  answer: string;
};

export type CompileScannerInput = {
  prompt: string;
  answers?: CompileAnswer[];
  draft_id?: string | null;
};

export type TestfireResult = {
  draft_id: string;
  run: ScannerRun;
  summary: {
    status: string;
    is_test: boolean;
    test_mode: boolean;
    counts: ScannerRunCounts;
    error: string | null;
  };
  top_matches: ScannerCandidate[];
  source: ApiSource;
};

function asCompiler(value: unknown): ScannerCompiler {
  return value === "llm-assisted" ? "llm-assisted" : "deterministic";
}

function asWarnings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((w) => (typeof w === "string" ? w.trim() : ""))
    .filter((w) => w.length > 0);
}

function asClarifyQuestions(value: unknown): ClarifyQuestion[] {
  if (!Array.isArray(value)) return [];
  const out: ClarifyQuestion[] = [];
  for (const raw of value) {
    const rec = asRecord(raw);
    const kind = rec.kind;
    if (
      kind !== "schedule" &&
      kind !== "threshold" &&
      kind !== "universe" &&
      kind !== "delivery" &&
      kind !== "other"
    ) {
      continue;
    }
    const id = typeof rec.id === "string" ? rec.id : "";
    const question = typeof rec.question === "string" ? rec.question : "";
    if (!id || !question) continue;
    const suggestions = Array.isArray(rec.suggestions)
      ? rec.suggestions.filter((s): s is string => typeof s === "string")
      : [];
    out.push({ id, question, kind, suggestions });
  }
  return out;
}

/** Loop 116 — local clarify decisions mirroring the backend (mock path). */
function localClarifyKinds(prompt: string, spec: ScannerSpec): ClarifyQuestionKind[] {
  const lower = prompt.toLowerCase();
  const needs: ClarifyQuestionKind[] = [];
  const hasSchedule =
    /\bevery\s+\d+\s*(?:minutes?|hours?|mins?|hrs?)\b/.test(lower) ||
    /\bevery\s+hour\b/.test(lower) ||
    /\bdaily\b/.test(lower);
  if (!hasSchedule) needs.push("schedule");
  const vague = /\b(big|heavy|soon|large|huge|significant|high)\b/.test(lower);
  const numeric =
    /(?:volume\s+above|min(?:imum)?\s+volume|above\s+)\s*\d/.test(lower) ||
    /\btop\s+\d+\b/.test(lower);
  if (vague && !numeric) needs.push("threshold");
  if (spec.universe.categories.length === 0) needs.push("universe");
  if (/\b(?:email|notify|notification|delivery|sms|webhook|inbox|alert\s+me)\b/.test(lower)) {
    needs.push("delivery");
  }
  return needs;
}

function localQuestionsFor(kinds: ClarifyQuestionKind[]): ClarifyQuestion[] {
  const out: ClarifyQuestion[] = [];
  kinds.slice(0, 3).forEach((kind, i) => {
    if (kind === "schedule") {
      out.push({
        id: `q${i + 1}_schedule`,
        question: "How often should this scanner run?",
        kind,
        suggestions: ["Every 15 minutes", "Every 30 minutes", "Every hour", "Daily"],
      });
    } else if (kind === "threshold") {
      out.push({
        id: `q${i + 1}_threshold`,
        question: "What numeric threshold should we use (volume or top-N)?",
        kind,
        suggestions: ["Volume above 10,000", "Volume above 50,000", "Top 10 markets"],
      });
    } else if (kind === "universe") {
      out.push({
        id: `q${i + 1}_universe`,
        question: "Which market universe should we scan?",
        kind,
        suggestions: ["NBA", "Sports", "Election", "Crypto"],
      });
    } else if (kind === "delivery") {
      out.push({
        id: `q${i + 1}_delivery`,
        question: "How should matches be delivered? (in-app only today)",
        kind,
        suggestions: ["In-app only", "In-app when matches fire", "Stored in-app (paper sim)"],
      });
    }
  });
  return out;
}

type MockDraft = {
  draft_id: string;
  prompt: string;
  spec: ScannerSpec;
  round: number;
  answerTexts: string[];
};

let mockDrafts: Record<string, MockDraft> = {};

function applyLocalAnswer(spec: ScannerSpec, kind: ClarifyQuestionKind, answer: string): ScannerSpec {
  const next = normalizeSpec(spec);
  const lower = answer.toLowerCase();
  if (kind === "schedule") {
    if (/\bdaily\b/.test(lower)) next.schedule.interval_minutes = 1440;
    else if (/\bevery\s+hour\b|\bhourly\b/.test(lower)) next.schedule.interval_minutes = 60;
    else {
      const m = lower.match(/(\d+)\s*(?:minutes?|mins?)/);
      if (m) next.schedule.interval_minutes = Number(m[1]);
      else {
        const h = lower.match(/(\d+)\s*(?:hours?|hrs?)/);
        if (h) next.schedule.interval_minutes = Number(h[1]) * 60;
      }
    }
  } else if (kind === "threshold") {
    const vol = lower.match(/(?:volume\s+above|above)\s*(\d[\d,]*)/);
    if (vol) next.universe.minimum_volume = Number(vol[1].replace(/,/g, ""));
    const top = lower.match(/\btop\s+(\d+)\b/);
    if (top) next.limit = Number(top[1]);
  } else if (kind === "universe") {
    for (const cat of ["nba", "sports", "election", "crypto"] as const) {
      if (new RegExp(`\\b${cat}\\b`).test(lower) && !next.universe.categories.includes(cat)) {
        next.universe.categories.push(cat);
      }
    }
  } else if (kind === "delivery") {
    next.delivery.in_app = true;
    next.delivery.email = false;
  }
  return next;
}

function compileConversationalLocal(input: CompileScannerInput): CompileScannerResult {
  let draft = input.draft_id ? mockDrafts[input.draft_id] : undefined;
  if (!draft) {
    const prompt = input.prompt;
    const spec = compileSpecLocal(prompt);
    draft = {
      draft_id: nextMockId("draft"),
      prompt,
      spec,
      round: 0,
      answerTexts: [],
    };
  }
  let spec = draft.spec;
  if (input.answers?.length) {
    // Pending questions inferred from prior needs.
    const priorKinds = localClarifyKinds(
      [draft.prompt, ...draft.answerTexts].join("\n"),
      spec,
    );
    const qs = localQuestionsFor(priorKinds);
    for (const ans of input.answers) {
      const q = qs.find((item) => item.id === ans.question_id);
      if (!q) continue;
      spec = applyLocalAnswer(spec, q.kind, ans.answer);
      draft.answerTexts.push(ans.answer);
    }
  }
  const combined = [draft.prompt, ...draft.answerTexts].join("\n");
  const needs = localClarifyKinds(combined, spec);
  if (needs.length > 0 && draft.round < 2) {
    const questions = localQuestionsFor(needs);
    draft.spec = spec;
    draft.round += 1;
    mockDrafts[draft.draft_id] = draft;
    return {
      status: "needs_clarification",
      draft_id: draft.draft_id,
      spec,
      spec_partial: spec,
      questions,
      compiler: "deterministic",
      warnings: specWarningsLocal(spec),
      source: "mock",
    };
  }
  spec.delivery.in_app = true;
  spec.delivery.email = false;
  draft.spec = spec;
  draft.round = Math.max(draft.round, 2);
  mockDrafts[draft.draft_id] = draft;
  const warnings = specWarningsLocal(spec);
  if (needs.length > 0) warnings.push("best-effort: clarification rounds exhausted");
  return {
    status: "ready",
    draft_id: draft.draft_id,
    spec,
    spec_partial: null,
    questions: [],
    compiler: "deterministic",
    warnings,
    source: "mock",
  };
}

/** Compile plain English into a scanner spec preview. POST /compile. */
export async function compileScanner(
  text: string,
  token: string | null = null,
): Promise<CompileScannerResult> {
  return compileScannerConversational({ prompt: text }, token);
}

/** Loop 116 — conversational compile with optional answers + draft_id. */
export async function compileScannerConversational(
  input: CompileScannerInput,
  token: string | null = null,
): Promise<CompileScannerResult> {
  const live = await tryLiveJson<unknown>("/api/v1/scanners/compile", token, {
    method: "POST",
    body: JSON.stringify({
      prompt: input.prompt,
      answers: input.answers ?? undefined,
      draft_id: input.draft_id ?? undefined,
    }),
  });
  const specRec = asRecord(live);
  if (live && (specRec.spec !== undefined || specRec.spec_partial !== undefined)) {
    const status =
      specRec.status === "needs_clarification" ? "needs_clarification" : "ready";
    const rawSpec = status === "ready" ? specRec.spec : (specRec.spec_partial ?? specRec.spec);
    return {
      status,
      draft_id: typeof specRec.draft_id === "string" ? specRec.draft_id : null,
      spec: normalizeSpec(rawSpec),
      spec_partial:
        status === "needs_clarification"
          ? normalizeSpec(specRec.spec_partial ?? specRec.spec)
          : null,
      questions: asClarifyQuestions(specRec.questions),
      compiler: asCompiler(specRec.compiler),
      warnings: asWarnings(specRec.warnings),
      source: "live",
    };
  }
  return compileConversationalLocal(input);
}

/** Dry-run a ready compile draft. POST /compile/testfire. */
export async function testfireCompileDraft(
  draftId: string,
  token: string | null = null,
): Promise<TestfireResult> {
  const live = await tryLiveJson<unknown>("/api/v1/scanners/compile/testfire", token, {
    method: "POST",
    body: JSON.stringify({ draft_id: draftId }),
  });
  if (live) {
    const rec = asRecord(live);
    const run = normalizeScannerRun(rec.run);
    if (run) {
      const summaryRec = asRecord(rec.summary);
      const countsRec = asRecord(summaryRec.counts);
      const topRaw = Array.isArray(rec.top_matches) ? rec.top_matches : [];
      return {
        draft_id: typeof rec.draft_id === "string" ? rec.draft_id : draftId,
        run,
        summary: {
          status: typeof summaryRec.status === "string" ? summaryRec.status : run.status,
          is_test: summaryRec.is_test !== false,
          test_mode: summaryRec.test_mode !== false,
          counts: {
            universe: asNumber(countsRec.universe),
            candidates: asNumber(countsRec.candidates),
            aligned: asNumber(countsRec.aligned),
          },
          error: typeof summaryRec.error === "string" ? summaryRec.error : run.error,
        },
        top_matches: topRaw
          .map((c) => normalizeCandidate(c))
          .filter((c): c is ScannerCandidate => c !== null),
        source: "live",
      };
    }
  }
  // Mock testfire — synthetic candidates (draft may be absent after remount).
  const now = new Date().toISOString();
  const run: ScannerRun = {
    id: nextMockId("run"),
    scanner_id: nextMockId("scn"),
    started_at: now,
    finished_at: now,
    status: "completed",
    checkpoint: null,
    result: {
      candidates: [
        {
          market_slug: "nba-2025-01-15-lal-bos",
          title: "Lakers vs Celtics",
          reads: {},
          aligned: true,
        },
      ],
      top_pick: {
        market_slug: "nba-2025-01-15-lal-bos",
        title: "Lakers vs Celtics",
        reads: {},
        aligned: true,
      },
      counts: { universe: 1, candidates: 1, aligned: 1 },
    },
    error: null,
    duration_ms: 12,
    is_test: true,
    repairs: [],
  };
  return {
    draft_id: draftId,
    run,
    summary: {
      status: "completed",
      is_test: true,
      test_mode: true,
      counts: { universe: 1, candidates: 1, aligned: 1 },
      error: null,
    },
    top_matches: run.result?.candidates ?? [],
    source: "mock",
  };
}

export type CreateScannerInput = {
  name: string;
  description?: string | null;
  spec: ScannerSpec;
  is_public?: boolean;
  cooldown_minutes?: number;
};

/** Create a scanner from a compiled spec. POST / (auth). */
export async function createScanner(
  input: CreateScannerInput,
  token: string | null = null,
): Promise<{ scanner: Scanner; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/scanners/", token, {
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? null,
      spec: input.spec,
      is_public: input.is_public ?? false,
      cooldown_minutes: input.cooldown_minutes ?? input.spec.delivery.cooldown_minutes ?? 120,
    }),
  });
  const scanner = live ? normalizeScanner(live) : null;
  if (scanner) return { scanner, source: "live" };

  const now = new Date().toISOString();
  const local: Scanner = {
    id: nextMockId("scn"),
    name: input.name.trim() || input.spec.name,
    description: input.description ?? null,
    owner: "local-user",
    spec: normalizeSpec(input.spec),
    version: 1,
    status: "draft",
    is_public: input.is_public ?? false,
    cooldown_minutes: input.cooldown_minutes ?? input.spec.delivery.cooldown_minutes ?? 120,
    created_at: now,
    updated_at: now,
    latest_run: null,
    next_run_at: null,
    last_error: null,
  };
  mockStore = {
    scanners: [local, ...mockStore.scanners],
    runs: { ...mockStore.runs, [local.id]: [] },
  };
  return { scanner: local, source: "mock" };
}

/** List visible scanners. GET / (live first; seeded mock when empty/absent). */
export async function listScanners(
  token: string | null = null,
): Promise<{ scanners: Scanner[]; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/scanners/", token);
  const rawList = asList(live);
  if (rawList && rawList.length > 0) {
    const scanners = rawList
      .map(normalizeScanner)
      .filter((s): s is Scanner => s !== null);
    if (scanners.length > 0) return { scanners, source: "live" };
  }
  return { scanners: mockStore.scanners, source: "mock" };
}

/** Get one scanner with its latest run. GET /{id}. */
export async function getScanner(
  id: string,
  token: string | null = null,
): Promise<{ scanner: Scanner | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}`,
    token,
  );
  const scanner = live ? normalizeScanner(live) : null;
  if (scanner) return { scanner, source: "live" };
  return { scanner: mockStore.scanners.find((s) => s.id === id) ?? null, source: "mock" };
}

/** Trigger a run now. POST /{id}/run (auth). Draft scanners flip to active. */
export async function runScannerNow(
  id: string,
  token: string | null = null,
): Promise<{ run: ScannerRun | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/run`,
    token,
    { method: "POST" },
  );
  const run = live ? normalizeScannerRun(live) : null;
  if (run) return { run, source: "live" };

  const scanner = mockStore.scanners.find((s) => s.id === id);
  if (!scanner) return { run: null, source: "mock" };
  const startedAt = new Date().toISOString();
  const run2: ScannerRun = {
    ...mockExecute(scanner.spec, nextMockId("run"), startedAt),
    scanner_id: scanner.id,
  };
  const updated: Scanner = {
    ...scanner,
    status: scanner.status === "draft" ? "active" : scanner.status,
    updated_at: startedAt,
    latest_run: run2,
  };
  mockStore = {
    scanners: mockStore.scanners.map((s) => (s.id === id ? updated : s)),
    runs: { ...mockStore.runs, [id]: [run2, ...(mockStore.runs[id] ?? [])] },
  };
  return { run: run2, source: "mock" };
}

/** Pause a scanner. POST /{id}/pause (auth). */
export async function pauseScanner(
  id: string,
  token: string | null = null,
): Promise<{ scanner: Scanner | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/pause`,
    token,
    { method: "POST" },
  );
  const scanner = live ? normalizeScanner(live) : null;
  if (scanner) return { scanner, source: "live" };
  return { scanner: setMockStatus(id, "paused"), source: "mock" };
}

/** Resume a paused scanner. POST /{id}/resume (auth). */
export async function resumeScanner(
  id: string,
  token: string | null = null,
): Promise<{ scanner: Scanner | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/resume`,
    token,
    { method: "POST" },
  );
  const scanner = live ? normalizeScanner(live) : null;
  if (scanner) return { scanner, source: "live" };
  return { scanner: setMockStatus(id, "active"), source: "mock" };
}

function setMockStatus(id: string, status: ScannerStatus): Scanner | null {
  const existing = mockStore.scanners.find((s) => s.id === id);
  if (!existing) return null;
  const updated: Scanner = { ...existing, status, updated_at: new Date().toISOString() };
  mockStore = {
    scanners: mockStore.scanners.map((s) => (s.id === id ? updated : s)),
    runs: mockStore.runs,
  };
  return updated;
}

/** Runs history, newest first (backend caps at 20). GET /{id}/runs. */
export async function listScannerRuns(
  id: string,
  token: string | null = null,
): Promise<{ runs: ScannerRun[]; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/runs`,
    token,
  );
  const rawList = asList(live);
  if (rawList && rawList.length > 0) {
    const runs = rawList
      .map(normalizeScannerRun)
      .filter((r): r is ScannerRun => r !== null);
    if (runs.length > 0) return { runs, source: "live" };
  }
  return { runs: mockStore.runs[id] ?? [], source: "mock" };
}

// ---------------------------------------------------------------------------
// Pre-publish + versioning endpoints (Loop V86 — X1/X2).
// test-run / test-email / publish / rollback / versions. Live first, mock
// fallback. publish surfaces the backend's 409 "run a test first" so the UI
// can disable the button until a test run exists.
// ---------------------------------------------------------------------------

/** Live fetch that returns status + body so business errors (409) surface. */
async function tryLiveResponse(
  path: string,
  token: string | null,
  init?: RequestInit,
): Promise<{ ok: boolean; status: number; body: unknown } | null> {
  const base = await liveBase();
  if (!base) return null;
  try {
    const res = await scannersFetch(apiUrl(path, base), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
    const text = await res.text();
    let body: unknown = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    return { ok: res.ok, status: res.status, body };
  } catch {
    return null;
  }
}

/** Human-readable message from a FastAPI error body (detail string/array). */
function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    const formatted = formatApiDetail(detail, "");
    if (formatted) return formatted;
  }
  if (typeof body === "string" && body.trim()) return body;
  return fallback;
}

export type TestEmailResult = {
  /** True when an email was actually dispatched. */
  sent: boolean;
  /** False when email delivery is not configured for this scanner. */
  configured: boolean;
  source: ApiSource;
};

/** Send a test email preview. POST /{id}/test-email (auth). */
export async function testEmailScanner(
  id: string,
  token: string | null = null,
): Promise<TestEmailResult> {
  const live = await tryLiveResponse(
    `/api/v1/scanners/${encodeURIComponent(id)}/test-email`,
    token,
    { method: "POST" },
  );
  if (live) {
    const rec = asRecord(live.body);
    return {
      sent: live.ok && rec.sent === true,
      configured: live.ok ? rec.configured !== false : rec.configured === true,
      source: "live",
    };
  }
  // Mock: email is "configured" only when the spec opts into email delivery.
  const scanner = mockStore.scanners.find((s) => s.id === id);
  const configured = scanner?.spec.delivery.email === true;
  return { sent: configured, configured, source: "mock" };
}

/** Execute a one-off test run over the current universe. POST /{id}/test-run. */
export async function testRunScanner(
  id: string,
  token: string | null = null,
): Promise<{ run: ScannerRun | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/test-run`,
    token,
    { method: "POST" },
  );
  const run = live ? normalizeScannerRun(live) : null;
  if (run) return { run, source: "live" };

  // Mock: execute the spec as a test snapshot (is_test=true) without
  // publishing — the scanner stays in draft until an explicit publish.
  const scanner = mockStore.scanners.find((s) => s.id === id);
  if (!scanner) return { run: null, source: "mock" };
  const startedAt = new Date().toISOString();
  const started = Date.parse(startedAt);
  const executed = mockExecute(scanner.spec, nextMockId("run-test"), startedAt);
  const testRun: ScannerRun = {
    ...executed,
    scanner_id: scanner.id,
    is_test: true,
    finished_at: new Date(started + 4200).toISOString(),
    duration_ms: 4200,
  };
  const updated: Scanner = {
    ...scanner,
    updated_at: startedAt,
    latest_run: testRun,
  };
  mockStore = {
    scanners: mockStore.scanners.map((s) => (s.id === id ? updated : s)),
    runs: { ...mockStore.runs, [id]: [testRun, ...(mockStore.runs[id] ?? [])] },
  };
  return { run: testRun, source: "mock" };
}

export type PublishResult =
  | { ok: true; scanner: Scanner; source: ApiSource }
  | { ok: false; reason: "no_test_run"; message: string; source: ApiSource };

/** Has this scanner logged at least one test run? (publish gate, mock parity). */
function mockHasTestRun(id: string): boolean {
  return (mockStore.runs[id] ?? []).some((r) => r.is_test);
}

/** Publish a scanner (draft → active). POST /{id}/publish (auth).
 *  409 until a test run exists — surfaced as `{ok:false, reason:"no_test_run"}`. */
export async function publishScanner(
  id: string,
  token: string | null = null,
): Promise<PublishResult> {
  const live = await tryLiveResponse(
    `/api/v1/scanners/${encodeURIComponent(id)}/publish`,
    token,
    { method: "POST" },
  );
  if (live) {
    if (live.ok) {
      const scanner = normalizeScanner(live.body);
      if (scanner) return { ok: true, scanner, source: "live" };
    }
    if (live.status === 409) {
      return {
        ok: false,
        reason: "no_test_run",
        message: errorMessage(live.body, "Run a test before publishing."),
        source: "live",
      };
    }
  }
  // Mock: require a prior test run, else mirror the 409 contract.
  if (!mockHasTestRun(id)) {
    return {
      ok: false,
      reason: "no_test_run",
      message: "Run a test first before publishing this scanner.",
      source: "mock",
    };
  }
  const scanner = setMockStatus(id, "active");
  if (!scanner) return { ok: false, reason: "no_test_run", message: "Scanner not found.", source: "mock" };
  return { ok: true, scanner, source: "mock" };
}

/** Roll back the live spec to a historical version. POST /{id}/rollback?version=N. */
export async function rollbackScanner(
  id: string,
  version: number,
  token: string | null = null,
): Promise<{ scanner: Scanner | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/rollback?version=${Number(version)}`,
    token,
    { method: "POST" },
  );
  const scanner = live ? normalizeScanner(live) : null;
  if (scanner) return { scanner, source: "live" };

  const existing = mockStore.scanners.find((s) => s.id === id);
  if (!existing) return { scanner: null, source: "mock" };
  const target = Math.max(1, Math.floor(Number(version) || existing.version));
  const updated: Scanner = {
    ...existing,
    version: target,
    status: "active",
    updated_at: new Date().toISOString(),
  };
  mockStore = {
    scanners: mockStore.scanners.map((s) => (s.id === id ? updated : s)),
    runs: mockStore.runs,
  };
  return { scanner: updated, source: "mock" };
}

/** Spec version history. GET /{id}/versions (live first; mock-derived fallback). */
export async function listScannerVersions(
  id: string,
  token: string | null = null,
): Promise<{ versions: ScannerVersion[]; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/scanners/${encodeURIComponent(id)}/versions`,
    token,
  );
  const rawList = asList(live);
  if (rawList && rawList.length > 0) {
    const versions = rawList
      .map((raw) => {
        const rec = asRecord(raw);
        const v = asNumber(rec.version, 0);
        if (v <= 0) return null;
        return {
          version: v,
          created_at:
            typeof rec.created_at === "string" ? rec.created_at : new Date(0).toISOString(),
          current: rec.current === true,
        };
      })
      .filter((v): v is ScannerVersion => v !== null)
      .sort((a, b) => b.version - a.version);
    if (versions.length > 0) return { versions, source: "live" };
  }
  // Mock: synthesize v1..current from the scanner's version count, marking
  // the live version current so the popover can offer rollback to older rows.
  const scanner = mockStore.scanners.find((s) => s.id === id);
  if (!scanner) return { versions: [], source: "mock" };
  const current = Math.max(1, scanner.version);
  const created = Date.parse(scanner.created_at);
  const versions: ScannerVersion[] = [];
  for (let v = current; v >= 1; v -= 1) {
    const offset = (v - 1) * 86_400_000;
    versions.push({
      version: v,
      created_at: Number.isFinite(created)
        ? new Date(created + offset).toISOString()
        : scanner.created_at,
      current: v === current,
    });
  }
  return { versions, source: "mock" };
}
