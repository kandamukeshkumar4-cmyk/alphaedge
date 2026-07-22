/**
 * Loop V79 — Research Terminal typed client.
 *
 * Backend contract (A1, `backend/app/schemas/terminal.py`):
 *   Session: `{id, question, market_slug, status, summary, created_at,
 *             updated_at, steps: ResearchStepOut[]}`
 *   Step:    `{id, sequence, title, kind: table|chart|text, status, payload,
 *             citations, created_at}`  (GOAL.md step contract)
 *   Scoreboard / bull / bear / verdict land in the session `summary` dict (A3).
 *
 * Endpoints: GET/POST `/api/v1/terminal/sessions`, GET `.../{id}`,
 * GET `.../{id}/stream` (SSE, A4).
 *
 * The live API is attempted first (Bearer token like the other authed
 * clients); on any failure the caller gets an in-memory PAPER mock so the UI
 * works while A2–A4 land in parallel. All fetch wiring lives in this one
 * file — UI components never call `fetch` themselves.
 *
 * PAPER_TRADING_ONLY — this terminal is research-only; there is no order path.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

export const TERMINAL_CANONICAL_MARKET = "nba-2025-01-15-lal-bos";
export const TERMINAL_CANONICAL_QUESTION =
  "What does the confluence of price, whale flow, news, and model say about Lakers vs Celtics (nba-2025-01-15-lal-bos)?";

// ---------------------------------------------------------------------------
// Types (GOAL.md contract)
// ---------------------------------------------------------------------------

export type StepKind = "table" | "chart" | "text";

export type Citation = {
  source: string;
  label: string;
  url?: string;
};

export type TablePayload = {
  columns: string[];
  rows: Array<Array<string | number | null>>;
  /** Optional one-line human read of the data (A2 may emit it). */
  summary?: string;
};

export type ChartPoint = { t: number; v: number };
export type ChartPayload = {
  series_name?: string;
  points: ChartPoint[];
  /** When true, values are paper PnL-like — UI must label PAPER ONLY. */
  paper_pnl?: boolean;
  /** Optional one-line human read of the data (A2 may emit it). */
  summary?: string;
};

export type TextPayload = {
  body: string;
  /** Optional one-line human read of the data (A2 may emit it). */
  summary?: string;
};

export type StepPayload = TablePayload | ChartPayload | TextPayload;

export type ResearchStep = {
  id: string;
  sequence: number;
  title: string;
  kind: StepKind;
  status: string;
  payload: StepPayload;
  citations: Citation[];
  created_at: string;
  /** Optional execution time; UI shows it on the card's right when present. */
  duration_ms?: number | null;
};

export type LensRead = "bullish" | "bearish" | "neutral" | "cautious";

export type ScoreboardLens = {
  lens: string;
  read: LensRead;
  why: string;
};

/** Normalized view of the backend session `summary` dict (A3 payload). */
export type SessionSummaryInfo = {
  scoreboard: ScoreboardLens[];
  bull_case: string | null;
  bear_case: string | null;
  verdict: string | null;
};

export type ResearchSessionStatus = "draft" | "running" | "completed" | "failed";

export type ResearchSession = {
  id: string;
  question: string;
  market_slug: string | null;
  status: ResearchSessionStatus;
  summary: SessionSummaryInfo;
  created_at: string;
  updated_at: string;
  steps: ResearchStep[];
};

export type SessionSummary = {
  id: string;
  question: string;
  market_slug: string | null;
  status: ResearchSessionStatus;
  created_at: string;
  updated_at: string;
  step_count: number;
};

export type StreamEvent =
  | { type: "step"; step: ResearchStep }
  | {
      type: "scoreboard";
      scoreboard: ScoreboardLens[];
      bull_case?: string | null;
      bear_case?: string | null;
      verdict?: string | null;
    }
  | { type: "done"; session: ResearchSession }
  | { type: "error"; message: string };

export type SenseId = "odds" | "whale" | "news" | "sentiment" | "model" | "arb";

/** Data+ popover order matches UI-DIRECTION: Whale/News/Sentiment/Model/Price. */
export const SENSE_CHIPS: { id: SenseId; label: string; blurb: string }[] = [
  { id: "whale", label: "Whale", blurb: "Large flow" },
  { id: "news", label: "News", blurb: "Headlines" },
  { id: "sentiment", label: "Sentiment", blurb: "Tone" },
  { id: "model", label: "Model", blurb: "Model vs market" },
  { id: "odds", label: "Price", blurb: "Price action & candles" },
  { id: "arb", label: "Arb", blurb: "Cross-venue" },
];

export type ApiSource = "live" | "mock";

export type TerminalResult<T> =
  | { ok: true; data: T; source: ApiSource }
  | { ok: false; reason: "unavailable" };

// ---------------------------------------------------------------------------
// Payload guards + normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

export function isTablePayload(p: StepPayload): p is TablePayload {
  return (
    Array.isArray((p as TablePayload).columns) && Array.isArray((p as TablePayload).rows)
  );
}

export function isChartPayload(p: StepPayload): p is ChartPayload {
  return Array.isArray((p as ChartPayload).points);
}

export function isTextPayload(p: StepPayload): p is TextPayload {
  return typeof (p as TextPayload).body === "string";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function normalizeCitation(raw: unknown): Citation {
  if (typeof raw === "string") return { source: "source", label: raw };
  const rec = asRecord(raw);
  return {
    source: typeof rec.source === "string" ? rec.source : "source",
    label:
      typeof rec.label === "string"
        ? rec.label
        : typeof rec.url === "string"
          ? rec.url
          : "citation",
    ...(typeof rec.url === "string" ? { url: rec.url } : {}),
  };
}

function normalizeStatus(raw: unknown): ResearchSessionStatus {
  return raw === "running" || raw === "completed" || raw === "failed" ? raw : "draft";
}

function normalizeKind(raw: unknown): StepKind {
  return raw === "table" || raw === "chart" ? raw : "text";
}

function normalizeChartPoint(raw: unknown): ChartPoint | null {
  const rec = asRecord(raw);
  const t = typeof rec.t === "number" ? rec.t : typeof rec.time === "number" ? rec.time : NaN;
  const v =
    typeof rec.v === "number" ? rec.v : typeof rec.value === "number" ? rec.value : NaN;
  return Number.isFinite(t) && Number.isFinite(v) ? { t, v } : null;
}

function normalizePayload(kind: StepKind, raw: unknown): StepPayload {
  const rec = asRecord(raw);
  if (kind === "table" && Array.isArray(rec.columns) && Array.isArray(rec.rows)) {
    return {
      columns: rec.columns.map((c) => String(c)),
      rows: rec.rows.map((r) =>
        Array.isArray(r)
          ? r.map((cell) =>
              typeof cell === "number" || typeof cell === "string" ? cell : null,
            )
          : [String(r)],
      ),
      ...(typeof rec.summary === "string" ? { summary: rec.summary } : {}),
    } satisfies TablePayload;
  }
  if (kind === "chart") {
    const rawPoints = Array.isArray(rec.points)
      ? rec.points
      : Array.isArray(rec.series)
        ? rec.series
        : [];
    const points = rawPoints
      .map(normalizeChartPoint)
      .filter((p): p is ChartPoint => p !== null);
    return {
      ...(typeof rec.series_name === "string" ? { series_name: rec.series_name } : {}),
      points,
      paper_pnl: rec.paper_pnl === true,
      ...(typeof rec.summary === "string" ? { summary: rec.summary } : {}),
    } satisfies ChartPayload;
  }
  return {
    body:
      typeof rec.body === "string"
        ? rec.body
        : typeof rec.text === "string"
          ? rec.text
          : "",
    ...(typeof rec.summary === "string" ? { summary: rec.summary } : {}),
  } satisfies TextPayload;
}

function normalizeStep(raw: unknown, fallbackIndex: number): ResearchStep {
  const rec = asRecord(raw);
  const kind = normalizeKind(rec.kind);
  const sequence =
    typeof rec.sequence === "number"
      ? rec.sequence
      : typeof rec.index === "number"
        ? rec.index
        : fallbackIndex;
  return {
    id: typeof rec.id === "string" ? rec.id : `step-${sequence}`,
    sequence,
    title: typeof rec.title === "string" ? rec.title : `Step ${sequence}`,
    kind,
    status: typeof rec.status === "string" ? rec.status : "done",
    payload: normalizePayload(kind, rec.payload),
    citations: Array.isArray(rec.citations) ? rec.citations.map(normalizeCitation) : [],
    created_at:
      typeof rec.created_at === "string" ? rec.created_at : new Date(0).toISOString(),
    ...(typeof rec.duration_ms === "number" && Number.isFinite(rec.duration_ms)
      ? { duration_ms: rec.duration_ms }
      : typeof rec.durationMs === "number" && Number.isFinite(rec.durationMs)
        ? { duration_ms: rec.durationMs }
        : {}),
  };
}

const LENS_READS: readonly LensRead[] = ["bullish", "bearish", "neutral", "cautious"];

function normalizeLens(raw: unknown): ScoreboardLens | null {
  const rec = asRecord(raw);
  if (typeof rec.lens !== "string") return null;
  const read = LENS_READS.includes(rec.read as LensRead)
    ? (rec.read as LensRead)
    : "neutral";
  return {
    lens: rec.lens,
    read,
    why: typeof rec.why === "string" ? rec.why : "",
  };
}

function normalizeSummaryInfo(raw: unknown): SessionSummaryInfo {
  const rec = asRecord(raw);
  const scoreboard = Array.isArray(rec.scoreboard)
    ? rec.scoreboard
        .map(normalizeLens)
        .filter((l): l is ScoreboardLens => l !== null)
    : [];
  return {
    scoreboard,
    bull_case: typeof rec.bull_case === "string" ? rec.bull_case : null,
    bear_case: typeof rec.bear_case === "string" ? rec.bear_case : null,
    verdict: typeof rec.verdict === "string" ? rec.verdict : null,
  };
}

function normalizeSession(raw: unknown): ResearchSession | null {
  const rec = asRecord(raw);
  if (typeof rec.id !== "string") return null;
  const steps = Array.isArray(rec.steps)
    ? rec.steps.map((s, i) => normalizeStep(s, i + 1))
    : [];
  steps.sort((a, b) => a.sequence - b.sequence);
  return {
    id: rec.id,
    question: typeof rec.question === "string" ? rec.question : "",
    market_slug: typeof rec.market_slug === "string" ? rec.market_slug : null,
    status: normalizeStatus(rec.status),
    summary: normalizeSummaryInfo(rec.summary),
    created_at:
      typeof rec.created_at === "string" ? rec.created_at : new Date(0).toISOString(),
    updated_at:
      typeof rec.updated_at === "string" ? rec.updated_at : new Date(0).toISOString(),
    steps,
  };
}

// ---------------------------------------------------------------------------
// Derived helpers (pure)
// ---------------------------------------------------------------------------

export function toSessionSummary(session: ResearchSession): SessionSummary {
  return {
    id: session.id,
    question: session.question,
    market_slug: session.market_slug,
    status: session.status,
    created_at: session.created_at,
    updated_at: session.updated_at,
    step_count: session.steps.length,
  };
}

/** One-line human summary for a step (payload summary, text body, or title). */
export function stepSummaryText(step: ResearchStep): string {
  const rec = asRecord(step.payload);
  if (typeof rec.summary === "string" && rec.summary.trim()) return rec.summary;
  if (isTextPayload(step.payload) && step.payload.body.trim()) {
    const body = step.payload.body.trim();
    return body.length > 160 ? `${body.slice(0, 157)}…` : body;
  }
  return step.title;
}

/** Fold a stream event into session state (pure). */
export function applyStreamEvent(
  session: ResearchSession,
  event: StreamEvent,
): ResearchSession {
  switch (event.type) {
    case "step": {
      const steps = [
        ...session.steps.filter((s) => s.id !== event.step.id),
        event.step,
      ].sort((a, b) => a.sequence - b.sequence);
      return { ...session, status: "running", steps };
    }
    case "scoreboard":
      return {
        ...session,
        summary: {
          scoreboard: event.scoreboard,
          bull_case: event.bull_case ?? session.summary.bull_case,
          bear_case: event.bear_case ?? session.summary.bear_case,
          verdict: event.verdict ?? session.summary.verdict,
        },
      };
    case "done":
      return { ...event.session, status: "completed" };
    case "error":
      return { ...session, status: "failed" };
  }
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live terminal API is absent)
// ---------------------------------------------------------------------------

const MOCK_NOW = "2026-07-21T15:00:00.000Z";

function mockChartPoints(): ChartPoint[] {
  const base = Date.parse("2025-01-15T00:00:00Z") / 1000;
  return Array.from({ length: 24 }, (_, i) => ({
    t: base + i * 3600,
    v: 0.48 + Math.sin(i / 3) * 0.04 + i * 0.002,
  }));
}

function buildMockSteps(): ResearchStep[] {
  return [
    {
      id: "step-01",
      sequence: 1,
      title: "Price action — Lakers YES",
      kind: "chart",
      status: "done",
      payload: {
        series_name: "Lakers YES mid (paper)",
        points: mockChartPoints(),
        paper_pnl: false,
        summary: "YES mid drifted from 48¢ to ~52¢ into tip-off; no extreme wick.",
      } satisfies ChartPayload,
      citations: [{ source: "odds", label: "CLOB mid · nba-2025-01-15-lal-bos" }],
      created_at: MOCK_NOW,
      duration_ms: 1180,
    },
    {
      id: "step-02",
      sequence: 2,
      title: "Whale flow snapshot",
      kind: "table",
      status: "done",
      payload: {
        columns: ["Wallet", "Side", "Size (sim)", "Price", "When"],
        rows: [
          ["0xwhale…a1", "YES", 12_500, 0.51, "−2h"],
          ["0xwhale…b2", "YES", 8_000, 0.5, "−90m"],
          ["0xflow…c3", "NO", 4_200, 0.49, "−40m"],
        ],
        summary: "Two large YES buys; net flow mildly bullish for Lakers.",
      } satisfies TablePayload,
      citations: [{ source: "whale", label: "Smart-money feed" }],
      created_at: MOCK_NOW,
      duration_ms: 940,
    },
    {
      id: "step-03",
      sequence: 3,
      title: "News & sentiment",
      kind: "text",
      status: "done",
      payload: {
        body: "Desk skim: no late scratches. Local coverage leans Lakers home form. Sentiment aggregate: cautious-bullish. Research only — not a tip.",
      } satisfies TextPayload,
      citations: [
        { source: "news", label: "News wire" },
        { source: "sentiment", label: "Tone model" },
      ],
      created_at: MOCK_NOW,
      duration_ms: 1420,
    },
    {
      id: "step-04",
      sequence: 4,
      title: "Model vs market",
      kind: "table",
      status: "done",
      payload: {
        columns: ["Metric", "Value", "Note"],
        rows: [
          ["Model P(YES)", "0.56", "Ensemble"],
          ["Market mid", "0.52", "CLOB"],
          ["Edge (paper)", "+0.04", "PAPER ONLY"],
          ["Brier vs close (hist)", "0.21", "Walk-forward"],
        ],
        summary: "Model 0.56 vs market 0.52 — +4pt paper edge (simulated).",
      } satisfies TablePayload,
      citations: [{ source: "model", label: "Feature store · XGBoost" }],
      created_at: MOCK_NOW,
      duration_ms: 1660,
    },
    {
      id: "step-05",
      sequence: 5,
      title: "Arb / venue gap",
      kind: "text",
      status: "done",
      payload: {
        body: "Polymarket vs Kalshi matched pair shows <1¢ gap after fees — below research threshold. No dutching edge flagged.",
      } satisfies TextPayload,
      citations: [{ source: "arb", label: "Arb matcher" }],
      created_at: MOCK_NOW,
      duration_ms: 720,
    },
  ];
}

function buildMockScoreboard(): ScoreboardLens[] {
  return [
    { lens: "price action", read: "bullish", why: "YES mid grind higher into tip-off." },
    { lens: "whale flow", read: "bullish", why: "Net large YES size on the board." },
    { lens: "news", read: "neutral", why: "No late injury shock." },
    { lens: "sentiment", read: "cautious", why: "Tone positive but thin sample." },
    { lens: "model-vs-market", read: "bullish", why: "Model above mid by ~4pts (paper)." },
    { lens: "time-to-lock", read: "neutral", why: "Hours remain; liquidity OK." },
  ];
}

const MOCK_BULL =
  "Price grind + whale YES + model edge align for a paper-bullish Lakers YES lean. Simulated funds only.";
const MOCK_BEAR =
  "Sentiment sample is thin and time-to-lock is open — a late news spike could erase the paper edge.";
const MOCK_VERDICT = "Cautious bullish lean (paper).";

function makeMockSession(partial?: Partial<ResearchSession>): ResearchSession {
  return {
    id: partial?.id ?? "sess-mock-lal-bos",
    question: partial?.question ?? TERMINAL_CANONICAL_QUESTION,
    market_slug: partial?.market_slug ?? TERMINAL_CANONICAL_MARKET,
    status: partial?.status ?? "completed",
    summary: partial?.summary ?? {
      scoreboard: buildMockScoreboard(),
      bull_case: MOCK_BULL,
      bear_case: MOCK_BEAR,
      verdict: MOCK_VERDICT,
    },
    created_at: partial?.created_at ?? MOCK_NOW,
    updated_at: partial?.updated_at ?? MOCK_NOW,
    steps: partial?.steps ?? buildMockSteps(),
  };
}

/** Canonical seeded session — exported for fixtures and offline fallback. */
export const MOCK_SESSION: ResearchSession = makeMockSession();

let mockSessions: ResearchSession[] = [MOCK_SESSION];

export function resetTerminalMockStore(): void {
  mockSessions = [makeMockSession()];
}

/**
 * Register a completed mock session with a caller-chosen id (used by the
 * Skills gallery mock run path: POST /skills/{id}/run creates a terminal
 * session, so the offline mock mirrors that by seeding one here). No-op if a
 * session with that id already exists. Live parity: the backend creates the
 * real session; this only ever runs when there is no live API.
 */
export function seedMockTerminalSession(
  id: string,
  opts: { question?: string; market_slug?: string | null } = {},
): ResearchSession {
  const existing = mockSessions.find((s) => s.id === id);
  if (existing) return existing;
  const now = new Date().toISOString();
  const seeded = makeMockSession({
    id,
    question: opts.question ?? TERMINAL_CANONICAL_QUESTION,
    market_slug: opts.market_slug ?? TERMINAL_CANONICAL_MARKET,
    status: "completed",
    created_at: now,
    updated_at: now,
  });
  mockSessions = [seeded, ...mockSessions];
  return seeded;
}

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the terminal API)
// ---------------------------------------------------------------------------

type TerminalFetch = typeof fetch;

let terminalFetch: TerminalFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setTerminalFetch(fn: TerminalFetch): void {
  terminalFetch = fn;
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
    const res = await terminalFetch(apiUrl(path, base), {
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

/** List sessions (live first, mock fallback). Never rejects. */
export async function listSessions(
  token: string | null = null,
): Promise<{ sessions: ResearchSession[]; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/terminal/sessions", token);
  const rawList = Array.isArray(live)
    ? live
    : Array.isArray(asRecord(live).items)
      ? (asRecord(live).items as unknown[])
      : Array.isArray(asRecord(live).sessions)
        ? (asRecord(live).sessions as unknown[])
        : null;
  if (rawList && rawList.length > 0) {
    const sessions = rawList
      .map(normalizeSession)
      .filter((s): s is ResearchSession => s !== null);
    if (sessions.length > 0) return { sessions, source: "live" };
  }
  // Empty / missing live catalog → seeded mock so the UI is independently verifiable.
  return { sessions: mockSessions, source: "mock" };
}

/** Get one session by id (live first, mock fallback). */
export async function getSession(
  id: string,
  token: string | null = null,
): Promise<{ session: ResearchSession | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/terminal/sessions/${encodeURIComponent(id)}`,
    token,
  );
  const session = live ? normalizeSession(live) : null;
  if (session) return { session, source: "live" };
  return {
    session: mockSessions.find((s) => s.id === id) ?? null,
    source: "mock",
  };
}

export type CreateSessionInput = {
  question: string;
  market_slug?: string | null;
  senses?: SenseId[];
};

/**
 * Create a session. Live: POST `{question, market_slug}` (A1 contract; senses
 * are a frontend concern until A2 lands). Mock: register a draft locally.
 */
export async function createSession(
  input: CreateSessionInput,
  token: string | null = null,
): Promise<{ session: ResearchSession; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/terminal/sessions", token, {
    method: "POST",
    body: JSON.stringify({
      question: input.question,
      market_slug: input.market_slug ?? null,
    }),
  });
  const session = live ? normalizeSession(live) : null;
  if (session) return { session, source: "live" };

  const now = new Date().toISOString();
  const local = makeMockSession({
    id: `term_local_${Date.now().toString(36)}`,
    question: input.question,
    market_slug: input.market_slug ?? TERMINAL_CANONICAL_MARKET,
    status: "draft",
    steps: [],
    summary: { scoreboard: [], bull_case: null, bear_case: null, verdict: null },
    created_at: now,
    updated_at: now,
  });
  mockSessions = [local, ...mockSessions];
  return { session: local, source: "mock" };
}

// ---------------------------------------------------------------------------
// SSE stream (A4 live endpoint; mock generator fallback)
// ---------------------------------------------------------------------------

function parseSseChunk(buffer: string): { events: StreamEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const part of parts) {
    const dataLines = part
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trim());
    if (dataLines.length === 0) continue;
    try {
      events.push(normalizeStreamEvent(JSON.parse(dataLines.join("\n"))));
    } catch {
      // skip malformed events
    }
  }
  return { events, rest };
}

function normalizeStreamEvent(raw: unknown): StreamEvent {
  const rec = asRecord(raw);
  if (rec.type === "step") {
    return { type: "step", step: normalizeStep(rec.step, 1) };
  }
  if (rec.type === "scoreboard") {
    return {
      type: "scoreboard",
      scoreboard: normalizeSummaryInfo({ scoreboard: rec.scoreboard }).scoreboard,
      bull_case: typeof rec.bull_case === "string" ? rec.bull_case : null,
      bear_case: typeof rec.bear_case === "string" ? rec.bear_case : null,
      verdict: typeof rec.verdict === "string" ? rec.verdict : null,
    };
  }
  if (rec.type === "done") {
    const session = normalizeSession(rec.session);
    if (session) return { type: "done", session };
  }
  if (rec.type === "error") {
    return {
      type: "error",
      message: typeof rec.message === "string" ? rec.message : "stream error",
    };
  }
  return { type: "error", message: "unknown stream event" };
}

async function* streamMock(sessionId: string): AsyncGenerator<StreamEvent> {
  const existing = mockSessions.find((s) => s.id === sessionId);
  const template = makeMockSession({
    id: sessionId,
    question: existing?.question ?? TERMINAL_CANONICAL_QUESTION,
  });
  const built: ResearchStep[] = [];
  for (const step of template.steps) {
    await new Promise((r) => setTimeout(r, 40));
    built.push(step);
    yield { type: "step", step };
  }
  yield {
    type: "scoreboard",
    scoreboard: template.summary.scoreboard,
    bull_case: MOCK_BULL,
    bear_case: MOCK_BEAR,
    verdict: MOCK_VERDICT,
  };
  const done: ResearchSession = {
    ...template,
    status: "completed",
    steps: built,
    updated_at: new Date().toISOString(),
  };
  mockSessions = [done, ...mockSessions.filter((s) => s.id !== sessionId)];
  yield { type: "done", session: done };
}

/**
 * Stream step events for a session. Live SSE first; on any failure (or for
 * mock-local sessions) falls back to the in-memory mock run.
 */
export async function* streamSession(
  id: string,
  options: { token?: string | null; signal?: AbortSignal } = {},
): AsyncGenerator<StreamEvent> {
  if (!id.startsWith("term_local_")) {
    const base = await liveBase();
    if (base) {
      try {
        const res = await terminalFetch(
          apiUrl(`/api/v1/terminal/sessions/${encodeURIComponent(id)}/stream`, base),
          {
            headers: {
              Accept: "text/event-stream",
              ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
            },
            cache: "no-store",
            signal: options.signal ?? null,
          },
        );
        if (res.ok && res.body) {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const parsed = parseSseChunk(buf);
            buf = parsed.rest;
            for (const ev of parsed.events) yield ev;
          }
          return;
        }
      } catch {
        // fall through to mock
      }
    }
  }
  yield* streamMock(id);
}
