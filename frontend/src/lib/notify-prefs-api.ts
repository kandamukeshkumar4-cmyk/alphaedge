import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";
import { digestFamilyLabel } from "./alerts-digest-api";
import { ACCESS_TOKEN_KEY } from "./portfolio-api";
import { categorizeSignal, type SignalCategory } from "./signals-dashboard-view-model";

/**
 * Y03 — Notification preferences client (backend L03, GET/PUT
 * /api/v1/notify/prefs). Per-user opt-in set of alert families. AUTHED (JWT —
 * 401 when anonymous).
 *
 * HARD GUARDRAIL: this is a preference STORE only. Prefs are stored + read
 * in-app to decide which alert families a user surfaces — there is NO external
 * delivery of any kind. The PUT here is the ONLY mutation this loop performs and
 * it is a preference, not an order. See goals/loop-v7/API-NOTES.md → L03.
 */

// Canonical family set + order (matches L02/L03 backend).
export const ALERT_FAMILIES = [
  "news:mispricing",
  "anomaly:unusual_flow",
  "delta:*",
  "screener:*",
  "arb",
] as const;

export type AlertFamily = (typeof ALERT_FAMILIES)[number];

export type NotifyPrefsResponse = {
  families?: Record<string, boolean> | null;
  enabled?: string[] | null;
  all_families?: string[] | null;
  source?: string;
  paper_trading_only?: boolean;
  disclaimer?: string;
};

export type NotifyToggle = { key: string; label: string; enabled: boolean };

export type NotifyPrefsView = {
  /** False when the API is unreachable (authed but null response). */
  reachable: boolean;
  /** False for anonymous callers (UI shows a sign-in prompt). */
  authed: boolean;
  source: "default" | "stored";
  toggles: NotifyToggle[];
  /** Enabled family keys in canonical order. */
  enabled: string[];
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Notification preferences are STORED and applied in-app only — no email, SMS, or webhook is ever sent. Paper trading, simulated funds.";

function canonicalOrder(keys: string[]): string[] {
  const known = (ALERT_FAMILIES as readonly string[]).filter((f) => keys.includes(f));
  const extra = keys.filter((k) => !(ALERT_FAMILIES as readonly string[]).includes(k));
  return [...known, ...extra];
}

/**
 * Pure: raw L03 response (or anon/unreachable) → view model. `authed=false`
 * yields the sign-in branch; an authed null response is unreachable. Toggles
 * cover every known family so the UI can render every checkbox.
 */
export function buildNotifyPrefsView(
  raw: NotifyPrefsResponse | null,
  authed: boolean,
): NotifyPrefsView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!authed) {
    return { reachable: false, authed: false, source: "default", toggles: [], enabled: [], disclaimer };
  }
  if (!raw) {
    return { reachable: false, authed: true, source: "default", toggles: [], enabled: [], disclaimer };
  }

  const allFamilies =
    Array.isArray(raw.all_families) && raw.all_families.length > 0
      ? raw.all_families
      : [...ALERT_FAMILIES];
  const familyMap = raw.families ?? {};
  const enabledList = Array.isArray(raw.enabled) ? raw.enabled : null;

  const toggles: NotifyToggle[] = allFamilies.map((key) => ({
    key,
    label: digestFamilyLabel(key),
    // Prefer the explicit families map; fall back to the enabled list.
    enabled:
      typeof familyMap[key] === "boolean"
        ? Boolean(familyMap[key])
        : enabledList
          ? enabledList.includes(key)
          : true,
  }));

  const enabled = canonicalOrder(toggles.filter((t) => t.enabled).map((t) => t.key));
  const source = raw.source === "stored" ? "stored" : "default";
  return { reachable: true, authed: true, source, toggles, enabled, disclaimer };
}

/**
 * Pure optimistic toggle: flip one family's membership, returning the next
 * enabled set in canonical order. No mutation of the input.
 */
export function toggleFamily(enabled: string[], key: string): string[] {
  const set = new Set(enabled);
  if (set.has(key)) set.delete(key);
  else set.add(key);
  return canonicalOrder([...set]);
}

// ── Prefs → feed filtering ────────────────────────────────────────────────────

// Map a UI SignalCategory to the prefs family that governs it. Categories with
// no clean 1:1 pref family (dutching, other) are always surfaced — we never
// fabricate a semantic mapping just to hide them.
const CATEGORY_TO_FAMILY: Partial<Record<SignalCategory, AlertFamily>> = {
  screener: "screener:*",
  news: "news:mispricing",
  anomaly: "anomaly:unusual_flow",
  weather: "delta:*",
};

/** Pure: is a signal category surfaced under the given enabled family set? */
export function isCategoryEnabled(category: SignalCategory, enabled: string[]): boolean {
  const family = CATEGORY_TO_FAMILY[category];
  if (!family) return true; // no governing pref → always on
  return enabled.includes(family);
}

/**
 * Pure: keep only items whose category is enabled by the prefs. `null` enabled
 * (anon / prefs unavailable) is a pass-through — never hides anything.
 */
export function filterItemsByPrefs<T extends { signal_type: string }>(
  items: T[],
  enabled: string[] | null,
): T[] {
  if (!enabled) return items;
  return items.filter((it) => isCategoryEnabled(categorizeSignal(it.signal_type), enabled));
}

// ── Network ─────────────────────────────────────────────────────────────────

function readToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
}

/**
 * GET the caller's notify prefs. AUTHED: returns null with no token (anon),
 * no live API, on 401, or on a transport error.
 */
export async function fetchNotifyPrefs(
  token?: string | null,
  signal?: AbortSignal,
): Promise<NotifyPrefsResponse | null> {
  const jwt = token ?? readToken();
  if (!jwt) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/notify/prefs", base), {
      headers: { Authorization: `Bearer ${jwt}` },
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as NotifyPrefsResponse;
  } catch {
    return null;
  }
}

/**
 * PUT the caller's enabled family set (upsert). The ONLY mutation in this loop —
 * a stored preference, never an order. Returns the persisted prefs, or null if
 * anon / unreachable / rejected (e.g. 422 on an unknown family).
 */
export async function putNotifyPrefs(
  enabled: string[],
  token?: string | null,
  signal?: AbortSignal,
): Promise<NotifyPrefsResponse | null> {
  const jwt = token ?? readToken();
  if (!jwt) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(apiUrl("/api/v1/notify/prefs", base), {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${jwt}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ families: enabled }),
      cache: "no-store",
      signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as NotifyPrefsResponse;
  } catch {
    return null;
  }
}
