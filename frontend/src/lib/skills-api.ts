/**
 * Loop V83 — Skills gallery typed client.
 *
 * Backend contract (S1):
 *   GET  /api/v1/skills/                  → Skill[]
 *   GET  /api/v1/skills/{id}             → Skill
 *   POST /api/v1/skills/{id}/run         → { session_id, ... } (creates a
 *                                          terminal session the terminal page
 *                                          loads via ?session={id})
 *   POST /api/v1/terminal/sessions/{id}/save-as-skill  → Skill
 *
 * The live API is attempted first (Bearer token like the other authed
 * clients); on any failure the caller gets an in-memory PAPER mock so the
 * gallery works while the backend is offline. Mirrors `terminal-api.ts`:
 * all fetch wiring lives here — UI components never call `fetch`.
 *
 * PAPER_TRADING_ONLY — running a skill only ever opens a research terminal
 * session; there is no order path.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import { seedMockTerminalSession } from "@/lib/terminal-api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SkillStepKind = "table" | "chart" | "text";

export type SkillStep = {
  title: string;
  kind: SkillStepKind;
};

export type Skill = {
  id: string;
  name: string;
  description: string;
  /** Emoji or short glyph shown on the card. */
  icon: string;
  template: SkillStep[];
  run_count: number;
  is_public: boolean;
};

export type SkillRunResult = {
  session_id: string;
};

export type SaveSkillInput = {
  name: string;
  description?: string;
};

export type ApiSource = "live" | "mock";

export type SkillsResult<T> =
  | { ok: true; data: T; source: ApiSource }
  | { ok: false; reason: "unavailable" };

// ---------------------------------------------------------------------------
// Payload guards + normalizers (backend sends dicts — be tolerant)
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function normalizeKind(raw: unknown): SkillStepKind {
  return raw === "table" || raw === "chart" ? raw : "text";
}

function normalizeStep(raw: unknown): SkillStep | null {
  const rec = asRecord(raw);
  if (typeof rec.title !== "string") return null;
  return { title: rec.title, kind: normalizeKind(rec.kind) };
}

export function normalizeSkill(raw: unknown): Skill | null {
  const rec = asRecord(raw);
  if (typeof rec.id !== "string" && typeof rec.name !== "string") return null;
  const id = typeof rec.id === "string" ? rec.id : String(rec.name).toLowerCase();
  const steps = Array.isArray(rec.template)
    ? rec.template.map(normalizeStep).filter((s): s is SkillStep => s !== null)
    : [];
  const runCount =
    typeof rec.run_count === "number"
      ? rec.run_count
      : typeof rec.runCount === "number"
        ? rec.runCount
        : 0;
  return {
    id,
    name: typeof rec.name === "string" ? rec.name : id,
    description: typeof rec.description === "string" ? rec.description : "",
    icon: typeof rec.icon === "string" && rec.icon ? rec.icon : "✦",
    template: steps,
    run_count: Number.isFinite(runCount) ? runCount : 0,
    is_public: rec.is_public !== false,
  };
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live skills API is absent)
// ---------------------------------------------------------------------------

const MOCK_SKILLS: Skill[] = [
  {
    id: "confluence",
    name: "Full confluence scan",
    description: "Price, whale, news, sentiment, model — one paper verdict.",
    icon: "🎯",
    template: [
      { title: "Price action", kind: "chart" },
      { title: "Whale flow", kind: "table" },
      { title: "News & sentiment", kind: "text" },
      { title: "Model vs market", kind: "table" },
      { title: "Confluence verdict", kind: "text" },
    ],
    run_count: 128,
    is_public: true,
  },
  {
    id: "whale",
    name: "Whale flow digest",
    description: "Large simulated flow on the board, summarized.",
    icon: "🐋",
    template: [
      { title: "Flow snapshot", kind: "table" },
      { title: "Net direction", kind: "text" },
    ],
    run_count: 64,
    is_public: true,
  },
  {
    id: "price",
    name: "Pre-game price read",
    description: "Candles and drift into tip-off, in one card.",
    icon: "📈",
    template: [
      { title: "Candles", kind: "chart" },
      { title: "Drift read", kind: "text" },
    ],
    run_count: 41,
    is_public: true,
  },
  {
    id: "news",
    name: "News & sentiment skim",
    description: "Headlines plus tone, cautious reads flagged.",
    icon: "📰",
    template: [
      { title: "Headlines", kind: "text" },
      { title: "Tone model", kind: "table" },
    ],
    run_count: 37,
    is_public: true,
  },
  {
    id: "arb",
    name: "Arb watch",
    description: "Cross-venue gap check after fees.",
    icon: "⚖️",
    template: [
      { title: "Venue gap", kind: "table" },
      { title: "Dutch edge", kind: "text" },
    ],
    run_count: 22,
    is_public: true,
  },
];

let mockSkills: Skill[] = MOCK_SKILLS.map((s) => ({ ...s }));

/** Test / wiring hook — reset the in-memory mock catalog. */
export function resetSkillsMockStore(): void {
  mockSkills = MOCK_SKILLS.map((s) => ({ ...s }));
}

/** Mock-store read — used by community-api fork parity (no live backend). */
export function findMockSkill(id: string): Skill | null {
  return mockSkills.find((s) => s.id === id) ?? null;
}

/** Mock-store write — a forked/created skill appears in the gallery mock. */
export function insertMockSkill(skill: Skill): void {
  mockSkills = [skill, ...mockSkills.filter((s) => s.id !== skill.id)];
}

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the skills API)
// ---------------------------------------------------------------------------

type SkillsFetch = typeof fetch;

let skillsFetch: SkillsFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setSkillsFetch(fn: SkillsFetch): void {
  skillsFetch = fn;
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
    const res = await skillsFetch(apiUrl(path, base), {
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

/** List skills (live first, mock fallback). Never rejects. */
export async function listSkills(
  token: string | null = null,
): Promise<{ skills: Skill[]; source: ApiSource }> {
  const live = await tryLiveJson<unknown>("/api/v1/skills/", token);
  const rawList = Array.isArray(live)
    ? live
    : Array.isArray(asRecord(live).items)
      ? (asRecord(live).items as unknown[])
      : Array.isArray(asRecord(live).skills)
        ? (asRecord(live).skills as unknown[])
        : null;
  if (rawList && rawList.length > 0) {
    const skills = rawList
      .map(normalizeSkill)
      .filter((s): s is Skill => s !== null);
    if (skills.length > 0) return { skills, source: "live" };
  }
  return { skills: mockSkills, source: "mock" };
}

/** Get one skill by id (live first, mock fallback). */
export async function getSkill(
  id: string,
  token: string | null = null,
): Promise<{ skill: Skill | null; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/skills/${encodeURIComponent(id)}`,
    token,
  );
  const skill = live ? normalizeSkill(live) : null;
  if (skill) return { skill, source: "live" };
  return {
    skill: mockSkills.find((s) => s.id === id) ?? null,
    source: "mock",
  };
}

/**
 * Run a skill — creates a terminal session. Live: POST `{}`; the backend
 * returns `{session_id}`. Mock: seed a terminal mock session and return its id.
 */
export async function runSkill(
  id: string,
  token: string | null = null,
): Promise<{ session_id: string; source: ApiSource }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/skills/${encodeURIComponent(id)}/run`,
    token,
    { method: "POST", body: JSON.stringify({}) },
  );
  const rec = asRecord(live);
  const sessionId =
    typeof rec.session_id === "string"
      ? rec.session_id
      : typeof rec.sessionId === "string"
        ? rec.sessionId
        : typeof rec.id === "string"
          ? rec.id
          : null;
  if (sessionId) return { session_id: sessionId, source: "live" };

  // Mock parity: register a terminal session so /terminal?session={id} loads it.
  const skill = mockSkills.find((s) => s.id === id);
  const mockId = `skill_run_${id}_${nextMockNonce()}`;
  seedMockTerminalSession(mockId, {
    question: skill ? `${skill.name} — ${skill.description}` : undefined,
  });
  return { session_id: mockId, source: "mock" };
}

/**
 * Save a completed terminal session as a skill. Live: POST `{name, description}`
 * to the save-as-skill endpoint. Mock: register the skill locally so the gallery
 * reflects it, and report success.
 */
export async function saveSessionAsSkill(
  sessionId: string,
  input: SaveSkillInput,
  token: string | null = null,
): Promise<{ ok: true; source: ApiSource } | { ok: false; reason: "unavailable" }> {
  const live = await tryLiveJson<unknown>(
    `/api/v1/terminal/sessions/${encodeURIComponent(sessionId)}/save-as-skill`,
    token,
    { method: "POST", body: JSON.stringify(input) },
  );
  if (live) {
    const created = normalizeSkill(live);
    if (created) mockSkills = [created, ...mockSkills.filter((s) => s.id !== created.id)];
    return { ok: true, source: "live" };
  }

  // Mock fallback — record a local skill so the gallery stays consistent.
  const id = `skill_save_${nextMockNonce()}`;
  mockSkills = [
    {
      id,
      name: input.name,
      description: input.description ?? "",
      icon: "✦",
      template: [],
      run_count: 0,
      is_public: false,
    },
    ...mockSkills,
  ];
  return { ok: true, source: "mock" };
}

// `Date.now()`/`Math.random()` are unavailable in some test contexts; a plain
// module counter gives stable, collision-free mock ids.
let mockNonce = 0;
function nextMockNonce(): number {
  mockNonce += 1;
  return mockNonce;
}
