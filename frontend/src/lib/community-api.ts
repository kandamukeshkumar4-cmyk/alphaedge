/**
 * Loop V85 (L1) — Community typed client: fork + subscribe.
 *
 * Backend contract (D-U1, built in parallel):
 *   POST   /api/v1/skills/{id}/fork       → SkillOut            (auth)
 *   POST   /api/v1/scanners/{id}/fork     → scanner             (auth)
 *   GET    /api/v1/subscriptions          → [{ref_type,ref_id,name,created_at}]
 *   POST   /api/v1/subscriptions {ref_type,ref_id}
 *                                        → [{ref_type,ref_id,name,created_at}]
 *   DELETE /api/v1/subscriptions {ref_type,ref_id}
 *                                        → [{ref_type,ref_id,name,created_at}]
 *
 * Live first (Bearer token like the other authed clients); on any failure the
 * caller gets an in-memory PAPER mock so fork/subscribe work while the backend
 * is offline. Mirrors `terminal-api.ts` (Loop V79): all fetch wiring lives here.
 *
 * PAPER_TRADING_ONLY — forking/subscribing are research-organization actions;
 * they never touch the order path.
 */

import { apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import {
  findMockSkill,
  insertMockSkill,
  normalizeSkill,
  type Skill,
} from "@/lib/skills-api";
import {
  findMockScanner,
  insertMockScanner,
  normalizeScanner,
  type Scanner,
} from "@/lib/scanners-api";

// ---------------------------------------------------------------------------
// Types (backend contract)
// ---------------------------------------------------------------------------

export type RefType = "skill" | "scanner";

export type Subscription = {
  ref_type: RefType;
  ref_id: string;
  name: string;
  created_at: string;
};

export type ApiSource = "live" | "mock";

export type ForkSkillResult =
  | { ok: true; skill: Skill; source: ApiSource }
  | { ok: false; reason: "unavailable" | "not_found" };

export type ForkScannerResult =
  | { ok: true; scanner: Scanner; source: ApiSource }
  | { ok: false; reason: "unavailable" | "not_found" };

// ---------------------------------------------------------------------------
// Payload guards + normalizers
// ---------------------------------------------------------------------------

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asRefType(value: unknown): RefType {
  return value === "skill" || value === "scanner" ? value : "skill";
}

function normalizeSubscription(raw: unknown): Subscription | null {
  const rec = asRecord(raw);
  if (typeof rec.ref_id !== "string" || !rec.ref_id) return null;
  const refType = asRefType(rec.ref_type);
  return {
    ref_type: refType,
    ref_id: rec.ref_id,
    name: typeof rec.name === "string" && rec.name ? rec.name : rec.ref_id,
    created_at:
      typeof rec.created_at === "string" && rec.created_at
        ? rec.created_at
        : new Date(0).toISOString(),
  };
}

function asSubList(live: unknown): Subscription[] {
  const list = Array.isArray(live)
    ? live
    : Array.isArray(asRecord(live).items)
      ? (asRecord(live).items as unknown[])
      : Array.isArray(asRecord(live).subscriptions)
        ? (asRecord(live).subscriptions as unknown[])
        : [];
  return list
    .map(normalizeSubscription)
    .filter((s): s is Subscription => s !== null);
}

// ---------------------------------------------------------------------------
// Mock store (in-memory; used whenever the live community API is absent)
// ---------------------------------------------------------------------------

let mockSubscriptions: Subscription[] = [
  {
    ref_type: "skill",
    ref_id: "confluence",
    name: "Full confluence scan",
    created_at: "2026-07-19T10:00:00.000Z",
  },
  {
    ref_type: "scanner",
    ref_id: "scn-mock-whale",
    name: "NBA whale + trend confluence",
    created_at: "2026-07-19T11:30:00.000Z",
  },
];

/** Test / wiring hook — reset the in-memory mock subscriptions. */
export function resetCommunityMockStore(): void {
  mockSubscriptions = [
    {
      ref_type: "skill",
      ref_id: "confluence",
      name: "Full confluence scan",
      created_at: "2026-07-19T10:00:00.000Z",
    },
    {
      ref_type: "scanner",
      ref_id: "scn-mock-whale",
      name: "NBA whale + trend confluence",
      created_at: "2026-07-19T11:30:00.000Z",
    },
  ];
}

// `Date.now()`/`Math.random()` are unavailable in some test contexts; a plain
// module counter gives stable, collision-free mock ids + timestamps.
let mockNonce = 0;
function nextNonce(): number {
  mockNonce += 1;
  return mockNonce;
}

const MOCK_EPOCH = Date.UTC(2026, 6, 19, 12, 0, 0); // 2026-07-19T12:00:00Z
function mockTimestamp(): string {
  return new Date(MOCK_EPOCH + nextNonce() * 1000).toISOString();
}

function findMockSub(ref_type: RefType, ref_id: string): Subscription | undefined {
  return mockSubscriptions.find(
    (s) => s.ref_type === ref_type && s.ref_id === ref_id,
  );
}

// ---------------------------------------------------------------------------
// Fetch layer (the only place the UI talks to the community API)
// ---------------------------------------------------------------------------

type CommunityFetch = typeof fetch;

let communityFetch: CommunityFetch = (...args) => fetch(...args);

/** Test / wiring hook — swap the fetch layer without touching UI files. */
export function setCommunityFetch(fn: CommunityFetch): void {
  communityFetch = fn;
}

async function liveBase(): Promise<string | null> {
  const base = (await ensureApiBase()) || undefined;
  return base && hasLiveApi(base) ? base : null;
}

async function tryLiveJson(
  path: string,
  token: string | null,
  init?: RequestInit,
): Promise<unknown | null> {
  const base = await liveBase();
  if (!base) return null;
  try {
    const res = await communityFetch(apiUrl(path, base), {
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
    return await res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Endpoints — live first, mock fallback. None of these reject.
// ---------------------------------------------------------------------------

/**
 * Fork a skill into the caller's account. Live: POST {id}/fork → SkillOut.
 * Mock: copy the source skill from the skills mock store, give it a new id,
 * and insert it so the fork appears in the gallery/library mock.
 */
export async function forkSkill(
  id: string,
  token: string | null = null,
): Promise<ForkSkillResult> {
  const live = await tryLiveJson(
    `/api/v1/skills/${encodeURIComponent(id)}/fork`,
    token,
    { method: "POST", body: JSON.stringify({}) },
  );
  if (live) {
    const skill = normalizeSkill(live);
    if (skill) return { ok: true, skill, source: "live" };
  }

  const source = findMockSkill(id);
  if (!source) return { ok: false, reason: "not_found" };
  const forked: Skill = {
    ...source,
    id: `skill_fork_${nextNonce()}`,
    name: `${source.name} (fork)`,
    run_count: 0,
    is_public: false,
  };
  insertMockSkill(forked);
  return { ok: true, skill: forked, source: "mock" };
}

/**
 * Fork a scanner into the caller's account. Live: POST {id}/fork → scanner.
 * Mock: copy the source scanner, new id, draft status, no runs.
 */
export async function forkScanner(
  id: string,
  token: string | null = null,
): Promise<ForkScannerResult> {
  const live = await tryLiveJson(
    `/api/v1/scanners/${encodeURIComponent(id)}/fork`,
    token,
    { method: "POST", body: JSON.stringify({}) },
  );
  if (live) {
    const scanner = normalizeScanner(live);
    if (scanner) return { ok: true, scanner, source: "live" };
  }

  const source = findMockScanner(id);
  if (!source) return { ok: false, reason: "not_found" };
  const now = mockTimestamp();
  const forked: Scanner = {
    ...source,
    id: `scn_fork_${nextNonce()}`,
    name: `${source.name} (fork)`,
    status: "draft",
    version: 1,
    is_public: false,
    created_at: now,
    updated_at: now,
    latest_run: null,
  };
  insertMockScanner(forked);
  return { ok: true, scanner: forked, source: "mock" };
}

/**
 * List the caller's subscriptions. Live: GET /subscriptions (auth).
 * Mock: the in-memory subscription list.
 */
export async function listSubscriptions(
  token: string | null = null,
): Promise<{ subscriptions: Subscription[]; source: ApiSource }> {
  const live = await tryLiveJson("/api/v1/subscriptions", token);
  if (live) {
    const subs = asSubList(live);
    if (subs.length > 0) return { subscriptions: subs, source: "live" };
    // An empty live list is still a valid live response — honor it.
    if (Array.isArray(live) || Array.isArray(asRecord(live).items)) {
      return { subscriptions: subs, source: "live" };
    }
  }
  return { subscriptions: mockSubscriptions.map((s) => ({ ...s })), source: "mock" };
}

/**
 * Subscribe to a skill/scanner. Live: POST {ref_type,ref_id} → subscription list.
 * Mock: add to the in-memory store (idempotent) and return the updated list.
 */
export async function addSubscription(
  ref_type: RefType,
  ref_id: string,
  token: string | null = null,
): Promise<{ subscriptions: Subscription[]; source: ApiSource }> {
  const live = await tryLiveJson("/api/v1/subscriptions", token, {
    method: "POST",
    body: JSON.stringify({ ref_type, ref_id }),
  });
  if (live) {
    const subs = asSubList(live);
    if (subs.length > 0 || Array.isArray(live) || Array.isArray(asRecord(live).items)) {
      return { subscriptions: subs, source: "live" };
    }
  }

  if (!findMockSub(ref_type, ref_id)) {
    const name = mockSubName(ref_type, ref_id);
    mockSubscriptions = [
      ...mockSubscriptions,
      { ref_type, ref_id, name, created_at: mockTimestamp() },
    ];
  }
  return { subscriptions: mockSubscriptions.map((s) => ({ ...s })), source: "mock" };
}

/**
 * Unsubscribe. Live: DELETE {ref_type,ref_id} → subscription list.
 * Mock: remove from the in-memory store (idempotent).
 */
export async function removeSubscription(
  ref_type: RefType,
  ref_id: string,
  token: string | null = null,
): Promise<{ subscriptions: Subscription[]; source: ApiSource }> {
  const live = await tryLiveJson("/api/v1/subscriptions", token, {
    method: "DELETE",
    body: JSON.stringify({ ref_type, ref_id }),
  });
  if (live) {
    const subs = asSubList(live);
    if (subs.length > 0 || Array.isArray(live) || Array.isArray(asRecord(live).items)) {
      return { subscriptions: subs, source: "live" };
    }
  }

  mockSubscriptions = mockSubscriptions.filter(
    (s) => !(s.ref_type === ref_type && s.ref_id === ref_id),
  );
  return { subscriptions: mockSubscriptions.map((s) => ({ ...s })), source: "mock" };
}

/** Resolve a friendly name for a mock subscription from the source stores. */
function mockSubName(ref_type: RefType, ref_id: string): string {
  if (ref_type === "skill") return findMockSkill(ref_id)?.name ?? ref_id;
  return findMockScanner(ref_id)?.name ?? ref_id;
}

/** Pure helper for UI toggle state — is this ref in the subscription list? */
export function isSubscribed(
  subs: Subscription[],
  ref_type: RefType,
  ref_id: string,
): boolean {
  return subs.some((s) => s.ref_type === ref_type && s.ref_id === ref_id);
}
