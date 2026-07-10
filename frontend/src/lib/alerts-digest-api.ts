import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";
import { relativeTime } from "./alerts-api";

/**
 * Y02 — Alerts digest client (backend L02, GET /api/v1/alerts/digest?window=).
 *
 * Per-family alert counts + top-N most-alerted ("moved") markets over a bounded
 * lookback window, a read-only composition of the existing signal store. PUBLIC
 * GET, notify/read only — never places or stores an order. The endpoint never
 * 5xxes: a null here means "unreachable", an empty digest (total 0) is honest.
 *
 * `signal_count` is the honest movement proxy the store exposes (how many
 * alert-family signals a market fired) — NOT a fabricated price move. See
 * goals/loop-v7/API-NOTES.md → L02.
 */

export type DigestWindow = "24h" | "7d";

export type RawDigestMover = {
  slug?: string;
  signal_count?: number;
  families?: Record<string, number> | null;
  last_signal_at?: string | null;
};

export type AlertsDigestResponse = {
  families?: Record<string, number> | null;
  top_movers?: RawDigestMover[] | null;
  window?: string;
  window_hours?: number;
  since?: string | null;
  slugs?: string | null;
  total?: number;
  paper_trading_only?: boolean;
  disclaimer?: string;
};

// The five canonical L02/J02 families, in canonical display order. Labels reuse
// the SignalEvidence family vocabulary (News / Flow / Screener) and name the two
// buckets that have no single SignalCategory (delta:* deltas, arb) honestly.
const FAMILY_ORDER = [
  "news:mispricing",
  "anomaly:unusual_flow",
  "delta:*",
  "screener:*",
  "arb",
] as const;

const FAMILY_LABEL: Record<string, string> = {
  "news:mispricing": "News mispricing",
  "anomaly:unusual_flow": "Unusual flow",
  "delta:*": "Price deltas",
  "screener:*": "Screener",
  arb: "Arb",
};

/** Pure: humanise a family key, falling back to a readable form for unknowns. */
export function digestFamilyLabel(key: string): string {
  return FAMILY_LABEL[key] ?? key.replaceAll(":", " · ").replaceAll("_", " ");
}

/** Deterministic sort index for a family key (unknowns sort last, stable). */
function familyRank(key: string): number {
  const i = (FAMILY_ORDER as readonly string[]).indexOf(key);
  return i === -1 ? FAMILY_ORDER.length : i;
}

export const DIGEST_WINDOWS: readonly DigestWindow[] = ["24h", "7d"] as const;

const WINDOW_LABEL: Record<DigestWindow, string> = {
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
};

export function digestWindowLabel(window: DigestWindow): string {
  return WINDOW_LABEL[window];
}

export type DigestFamilyRow = { key: string; label: string; count: number };
export type DigestMoverRow = {
  slug: string;
  signalCount: number;
  families: string[];
  lastLabel: string;
};

export type AlertsDigestView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  total: number;
  windowLabel: string;
  familyRows: DigestFamilyRow[];
  movers: DigestMoverRow[];
  /** True when reachable but nothing fired in the window (honest empty). */
  empty: boolean;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Alerts are notify/read only — a digest of signal activity over the window, not a trade instruction. Paper trading, simulated funds, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/**
 * Pure transform: raw L02 digest → view model. Families sorted by count desc
 * then canonical family order; movers preserve the backend's deterministic
 * ranking (signal_count desc, recency, slug). Honest empty for total 0.
 */
export function buildAlertsDigestView(
  raw: AlertsDigestResponse | null,
  now: number = Date.now(),
): AlertsDigestView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  const windowLabel =
    typeof raw?.window === "string" && raw.window.trim() ? raw.window.trim() : "24h";
  if (!raw) {
    return {
      reachable: false,
      total: 0,
      windowLabel,
      familyRows: [],
      movers: [],
      empty: false,
      disclaimer,
    };
  }

  const familyRows: DigestFamilyRow[] = Object.entries(raw.families ?? {})
    .filter(([, count]) => isFiniteNum(count) && count > 0)
    .map(([key, count]) => ({ key, label: digestFamilyLabel(key), count }))
    .sort((a, b) => b.count - a.count || familyRank(a.key) - familyRank(b.key));

  const movers: DigestMoverRow[] = (Array.isArray(raw.top_movers) ? raw.top_movers : [])
    .filter((m): m is RawDigestMover & { slug: string } => Boolean(m && typeof m.slug === "string" && m.slug))
    .map((m) => ({
      slug: m.slug,
      signalCount: isFiniteNum(m.signal_count) ? m.signal_count : 0,
      families: Object.keys(m.families ?? {}).sort((a, b) => familyRank(a) - familyRank(b)),
      lastLabel: m.last_signal_at ? relativeTime(m.last_signal_at, now) : "",
    }));

  const total = isFiniteNum(raw.total)
    ? raw.total
    : familyRows.reduce((n, r) => n + r.count, 0);

  return {
    reachable: true,
    total,
    windowLabel,
    familyRows,
    movers,
    empty: total <= 0 && familyRows.length === 0 && movers.length === 0,
    disclaimer,
  };
}

// ── Network ─────────────────────────────────────────────────────────────────

/**
 * Fetch the alerts digest for a window. PUBLIC GET (no auth). Returns null with
 * no live API / on a transport error (unreachable); the endpoint itself never
 * 5xxes, so a non-null response with total 0 is an honest empty digest.
 */
export async function fetchAlertsDigest(
  window: DigestWindow,
  opts?: { top?: number; signal?: AbortSignal },
): Promise<AlertsDigestResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams({ window });
  if (opts?.top) params.set("top", String(opts.top));
  try {
    const res = await fetch(
      `${apiUrl("/api/v1/alerts/digest", base)}?${params.toString()}`,
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as AlertsDigestResponse;
  } catch {
    return null;
  }
}
