import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";
import { familyLabel, relativeTime } from "./alerts-api";
import { extractSignalEvidence, type SignalEvidence } from "./signal-evidence";
import { categorizeSignal } from "./signals-dashboard-view-model";

/**
 * Z02 — Shareable market snapshot client (backend M02,
 * GET /api/v1/markets/{slug}/share-snapshot).
 *
 * A SMALL read-only intelligence snapshot for one market, sized for the
 * `/s/[slug]` share card: title, current YES price, model-vs-market edge
 * one-liner, top signal (with H03 citation evidence), cross-venue arb flag, and
 * a smart-money one-liner. Unknown slug → honest 200 {found:false} (never a
 * 404). Research only, paper trading only — a shareable read, never a trade.
 *
 * PATH NOTE: this targets `/share-snapshot`, NOT the pre-existing full
 * `/snapshot` route (a different locked contract). See goals/loop-v8/API-NOTES.md.
 *
 * All transforms are pure and tolerant of missing fields — nothing is
 * fabricated. `buildShareSnapshotView(null)` marks the card unreachable.
 */

// ── Raw response (matches goals/loop-v8/API-NOTES.md → M02) ──────────────────

export type ShareEdge = {
  model_p?: number | null;
  market_p?: number | null;
  edge?: number | null;
};

export type ShareTopSignal = {
  family?: string | null;
  signal_type?: string | null;
  created_at?: string | null;
  citation?: Record<string, unknown> | null;
};

export type ShareSnapshotResponse = {
  found?: boolean;
  slug?: string;
  title?: string | null;
  yes_price?: number | null;
  edge?: ShareEdge | null;
  top_signal?: ShareTopSignal | null;
  arb_matched?: boolean;
  smart_money_note?: string | null;
  cached?: boolean;
  paper_trading_only?: boolean;
  signal_only?: boolean;
  disclaimer?: string;
  generated_at?: string;
};

// ── View model (pure — unit-tested) ──────────────────────────────────────────

export type ShareTopSignalView = {
  familyLabel: string;
  typeLabel: string;
  timeLabel: string;
  evidence: SignalEvidence | null;
};

export type ShareSnapshotView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  /** Honest false when the slug is unknown (200 {found:false}). */
  found: boolean;
  slug: string;
  title: string;
  yesLabel: string | null;
  edgeLabel: string | null;
  edgeTone: "up" | "down" | "neutral";
  modelLabel: string | null;
  marketLabel: string | null;
  topSignal: ShareTopSignalView | null;
  arbMatched: boolean;
  smartMoneyNote: string | null;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Shareable research snapshot — a read-only view of the desk's intelligence for this market. Paper trading, simulated funds, notify only, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function pct(value: number | null | undefined): string | null {
  return isFiniteNum(value) ? `${Math.round(value * 100)}%` : null;
}

function typeLabel(signalType: string): string {
  return signalType.replaceAll(":", " · ").replaceAll("_", " ");
}

function buildTopSignal(
  raw: ShareTopSignal | null | undefined,
  now: number,
): ShareTopSignalView | null {
  if (!raw) return null;
  const signalType = typeof raw.signal_type === "string" ? raw.signal_type : "";
  if (!signalType) return null;
  const family = categorizeSignal(signalType);
  const createdAt = typeof raw.created_at === "string" ? raw.created_at : "";
  return {
    familyLabel: familyLabel(family),
    typeLabel: typeLabel(signalType),
    timeLabel: createdAt ? relativeTime(createdAt, now) : "",
    evidence: extractSignalEvidence(signalType, raw.citation ?? undefined),
  };
}

/**
 * Pure transform: raw M02 share snapshot → view model. Honest unreachable /
 * not-found / thin states; the edge one-liner and top-signal evidence degrade
 * to null when the underlying fields are absent. Nothing is fabricated.
 */
export function buildShareSnapshotView(
  raw: ShareSnapshotResponse | null,
  now: number = Date.now(),
): ShareSnapshotView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  const slug = typeof raw?.slug === "string" ? raw.slug : "";

  if (!raw) {
    return {
      reachable: false,
      found: false,
      slug,
      title: slug,
      yesLabel: null,
      edgeLabel: null,
      edgeTone: "neutral",
      modelLabel: null,
      marketLabel: null,
      topSignal: null,
      arbMatched: false,
      smartMoneyNote: null,
      disclaimer,
    };
  }

  const found = Boolean(raw.found);
  const edge = raw.edge ?? null;
  const edgeVal = edge && isFiniteNum(edge.edge) ? edge.edge : null;
  const edgeLabel =
    edgeVal === null ? null : `${edgeVal >= 0 ? "+" : ""}${(edgeVal * 100).toFixed(1)} pts`;
  const edgeTone: "up" | "down" | "neutral" =
    edgeVal === null ? "neutral" : edgeVal > 0 ? "up" : edgeVal < 0 ? "down" : "neutral";

  return {
    reachable: true,
    found,
    slug,
    title: typeof raw.title === "string" && raw.title.trim() ? raw.title : slug,
    yesLabel: pct(raw.yes_price),
    edgeLabel,
    edgeTone,
    modelLabel: pct(edge?.model_p),
    marketLabel: pct(edge?.market_p),
    topSignal: found ? buildTopSignal(raw.top_signal, now) : null,
    arbMatched: Boolean(raw.arb_matched),
    smartMoneyNote:
      typeof raw.smart_money_note === "string" && raw.smart_money_note.trim()
        ? raw.smart_money_note
        : null,
    disclaimer,
  };
}

// ── Network ─────────────────────────────────────────────────────────────────

/**
 * Fetch the compact share snapshot for a slug. PUBLIC GET (no auth). Returns
 * null with no live API / on a transport error (unreachable). The endpoint
 * never 5xxes — an unknown slug is an honest 200 {found:false}.
 */
export async function fetchShareSnapshot(
  slug: string,
  opts?: { signal?: AbortSignal },
): Promise<ShareSnapshotResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(
      apiUrl(`/api/v1/markets/${encodeURIComponent(slug)}/share-snapshot`, base),
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as ShareSnapshotResponse;
  } catch {
    return null;
  }
}
