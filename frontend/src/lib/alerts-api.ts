import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";
import { ACCESS_TOKEN_KEY } from "./portfolio-api";
import { extractSignalEvidence, type SignalEvidence } from "./signal-evidence";
import { categorizeSignal, type SignalCategory } from "./signals-dashboard-view-model";

/**
 * W02 — Alerts feed client (backend J02, GET /api/v1/alerts?since=&slugs=).
 *
 * Returns recent signal events (news:mispricing, anomaly:unusual_flow, delta:*,
 * screener:*, arb) filtered to the given slugs — or the caller's watchlist when
 * authed, the public stream when anon. Read-only, NOTIFY ONLY: alerts never
 * place orders. All grouping/labelling is pure and tolerant of missing fields.
 */
export type AlertEventItem = {
  id: string;
  signal_type: string;
  platform: string;
  market_id: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
};

export type AlertsResponse = {
  items?: RawAlertItem[];
  scope?: string;
  paper_trading_only?: boolean;
};

/**
 * Raw item as returned by the backend J02/K03 feed. The feed keys the market by
 * `slug` and carries H03 citation fields in a `citation` object; older/legacy
 * callers used `market_id`. `normalizeAlertItems` reconciles both into the
 * `AlertEventItem` the pure view-model consumes.
 */
export type RawAlertItem = {
  id?: string;
  signal_type?: string;
  platform?: string;
  slug?: string;
  market_id?: string;
  payload?: Record<string, unknown> | null;
  citation?: Record<string, unknown> | null;
  created_at?: string;
};

/**
 * Pure: normalize raw feed items into `AlertEventItem`. Maps `slug` → `market_id`
 * (the feed's canonical market key) and folds any `citation` fields into the
 * payload as a fallback so evidence renders even when a field lives only on the
 * citation. Drops items missing an id/market/timestamp. Never fabricates.
 */
export function normalizeAlertItems(raw: RawAlertItem[] | null | undefined): AlertEventItem[] {
  if (!Array.isArray(raw)) return [];
  const out: AlertEventItem[] = [];
  for (const it of raw) {
    const marketId = (it.market_id ?? it.slug ?? "").trim();
    const id = it.id;
    const createdAt = it.created_at;
    if (!id || !marketId || !createdAt) continue;
    const payload: Record<string, unknown> = { ...(it.citation ?? {}), ...(it.payload ?? {}) };
    out.push({
      id,
      signal_type: it.signal_type ?? "",
      platform: it.platform ?? "",
      market_id: marketId,
      payload,
      created_at: createdAt,
    });
  }
  return out;
}

export type AlertRowView = {
  id: string;
  family: SignalCategory;
  familyLabel: string;
  typeLabel: string;
  timeLabel: string;
  createdAt: string;
  evidence: SignalEvidence | null;
};

export type AlertGroupView = {
  slug: string;
  count: number;
  latestTs: number;
  latestLabel: string;
  families: SignalCategory[];
  rows: AlertRowView[];
};

const FAMILY_LABEL: Record<SignalCategory, string> = {
  screener: "Screener",
  weather: "Weather",
  dutching: "Dutching",
  news: "News",
  anomaly: "Flow",
  other: "Other",
};

export function familyLabel(family: SignalCategory): string {
  return FAMILY_LABEL[family];
}

/** Pure: humanised "Xm/Xh/Xd ago". `now` injectable for deterministic tests. */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const ts = Date.parse(iso);
  if (!Number.isFinite(ts)) return "";
  const mins = Math.max(0, Math.round((now - ts) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function typeLabel(signalType: string): string {
  return signalType.replaceAll(":", " · ").replaceAll("_", " ");
}

/** Pure: how many items landed after the last-seen timestamp (unread-ish). */
export function unreadAlertCount(items: AlertEventItem[], lastSeenTs: number): number {
  return items.reduce((n, it) => {
    const ts = Date.parse(it.created_at);
    return Number.isFinite(ts) && ts > lastSeenTs ? n + 1 : n;
  }, 0);
}

/** Pure: newest created_at across items (0 when none). */
export function newestAlertTs(items: AlertEventItem[]): number {
  return items.reduce((max, it) => {
    const ts = Date.parse(it.created_at);
    return Number.isFinite(ts) && ts > max ? ts : max;
  }, 0);
}

/** Pure: distinct families present, ordered by frequency then label. */
export function alertFamilies(items: AlertEventItem[]): SignalCategory[] {
  const counts = new Map<SignalCategory, number>();
  for (const it of items) {
    const fam = categorizeSignal(it.signal_type);
    counts.set(fam, (counts.get(fam) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || FAMILY_LABEL[a[0]].localeCompare(FAMILY_LABEL[b[0]]))
    .map(([fam]) => fam);
}

/**
 * Pure: group alert events by market (newest group first), optionally filtered
 * to one family. Rows within a group are newest first. Honest empty for [].
 */
export function buildAlertGroups(
  items: AlertEventItem[],
  filter: SignalCategory | "all" = "all",
  now: number = Date.now(),
): AlertGroupView[] {
  const groups = new Map<string, AlertRowView[]>();
  const famSet = new Map<string, Set<SignalCategory>>();

  for (const it of items) {
    if (!it.market_id) continue;
    const family = categorizeSignal(it.signal_type);
    if (filter !== "all" && family !== filter) continue;
    const row: AlertRowView = {
      id: it.id,
      family,
      familyLabel: FAMILY_LABEL[family],
      typeLabel: typeLabel(it.signal_type),
      timeLabel: relativeTime(it.created_at, now),
      createdAt: it.created_at,
      evidence: extractSignalEvidence(it.signal_type, it.payload ?? undefined),
    };
    const arr = groups.get(it.market_id) ?? [];
    arr.push(row);
    groups.set(it.market_id, arr);
    const fs = famSet.get(it.market_id) ?? new Set<SignalCategory>();
    fs.add(family);
    famSet.set(it.market_id, fs);
  }

  const out: AlertGroupView[] = [];
  for (const [slug, rows] of groups.entries()) {
    rows.sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
    const latestTs = Date.parse(rows[0]?.createdAt ?? "") || 0;
    out.push({
      slug,
      count: rows.length,
      latestTs,
      latestLabel: relativeTime(rows[0]?.createdAt ?? "", now),
      families: [...(famSet.get(slug) ?? new Set())],
      rows,
    });
  }
  out.sort((a, b) => b.latestTs - a.latestTs);
  return out;
}

// ── Network ─────────────────────────────────────────────────────────────────

/**
 * Fetch the alerts feed. Uses the JWT session (watchlist-scoped) when present,
 * otherwise the public stream. Returns [] with no live API / on error.
 */
export async function fetchAlertsFeed(opts?: {
  since?: string;
  slugs?: string[];
  limit?: number;
}): Promise<AlertEventItem[]> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return [];
  const token =
    typeof window !== "undefined" ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
  const params = new URLSearchParams();
  if (opts?.since) params.set("since", opts.since);
  if (opts?.slugs && opts.slugs.length > 0) params.set("slugs", opts.slugs.join(","));
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  try {
    const res = await fetch(apiUrl(`/api/v1/alerts/feed${qs ? `?${qs}` : ""}`, base), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as AlertsResponse;
    return normalizeAlertItems(data.items);
  } catch {
    return [];
  }
}

/**
 * X03 — fetch the caller's watchlist-scoped alerts (backend K03,
 * GET /api/v1/watchlist/alerts). AUTHED: requires a JWT — returns [] with no
 * token / no live API / on error. The backend pre-filters the J02 feed to the
 * caller's watchlist slugs so the UI needs a single call. Notify/read only.
 */
export async function fetchWatchlistAlerts(
  token: string | null,
  opts?: { since?: string; limit?: number },
): Promise<AlertEventItem[]> {
  if (!token) return [];
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return [];
  const params = new URLSearchParams();
  if (opts?.since) params.set("since", opts.since);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  try {
    const res = await fetch(apiUrl(`/api/v1/watchlist/alerts${qs ? `?${qs}` : ""}`, base), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as AlertsResponse;
    return normalizeAlertItems(data.items);
  } catch {
    return [];
  }
}
