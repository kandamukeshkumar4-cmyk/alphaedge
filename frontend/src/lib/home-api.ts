import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";
import {
  familyLabel,
  normalizeAlertItems,
  relativeTime,
  type AlertEventItem,
  type RawAlertItem,
} from "./alerts-api";
import {
  buildAlertsDigestView,
  type AlertsDigestResponse,
  type AlertsDigestView,
} from "./alerts-digest-api";
import { buildModelAbView, type ModelAbView } from "./model-ab-api";
import { extractSignalEvidence, type SignalEvidence } from "./signal-evidence";
import { categorizeSignal, type SignalCategory } from "./signals-dashboard-view-model";

/**
 * Z01 — Personalized home client (backend M01, GET /api/v1/home).
 *
 * ONE public GET (optional JWT) that composes the "your intelligence" landing:
 * recent signals with H03 citations, the L02 alerts digest, I02/J03 model-A/B
 * readiness, top markets by liquidity, and — when authed — the caller's K03
 * watchlist count + watchlist-scoped alerts. Read-only research surface; every
 * section degrades to an honest empty. Anonymous callers get the four
 * non-personal sections; personal fields are null/[] until signed in.
 *
 * All transforms below are pure and tolerant of missing fields — nothing is
 * fabricated. `buildHomeView(null)` marks the surface unreachable (API down).
 */

// ── Raw response (matches goals/loop-v8/API-NOTES.md → M01) ──────────────────

export type HomeTopMarket = {
  slug?: string;
  title?: string | null;
  category?: string | null;
  volume?: number | null;
  yes_price?: number | null;
  status?: string | null;
};

export type HomeModelAb = {
  resolved_count?: number | null;
  ab_threshold?: number | null;
  ab_ready?: boolean;
  model_default?: string | null;
  lightgbm_available?: boolean;
  applied?: boolean;
};

export type HomeResponse = {
  authenticated?: boolean;
  signals?: RawAlertItem[] | null;
  digest?: AlertsDigestResponse | null;
  model_ab?: HomeModelAb | null;
  top_markets?: HomeTopMarket[] | null;
  watchlist_count?: number | null;
  watchlist_alerts?: RawAlertItem[] | null;
  paper_trading_only?: boolean;
  signal_only?: boolean;
  disclaimer?: string;
  generated_at?: string;
};

// ── View model (pure — unit-tested) ──────────────────────────────────────────

export type HomeSignalRow = {
  id: string;
  slug: string;
  family: SignalCategory;
  familyLabel: string;
  typeLabel: string;
  timeLabel: string;
  createdAt: string;
  evidence: SignalEvidence | null;
};

export type HomeMarketRow = {
  slug: string;
  title: string;
  category: string | null;
  volumeLabel: string;
  yesLabel: string | null;
  status: string | null;
};

export type HomeView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  authenticated: boolean;
  signals: HomeSignalRow[];
  digest: AlertsDigestView;
  modelAb: ModelAbView;
  topMarkets: HomeMarketRow[];
  /** Authed only — null when anonymous. */
  watchlistCount: number | null;
  watchlistAlerts: HomeSignalRow[];
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Personalized intelligence home — a read-only research surface. Paper trading, simulated funds, notify only, no execution.";

const VOLUME_FMT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function typeLabel(signalType: string): string {
  return signalType.replaceAll(":", " · ").replaceAll("_", " ");
}

/** Pure: normalize raw feed items into renderable signal rows (newest first). */
export function buildSignalRows(
  raw: RawAlertItem[] | null | undefined,
  now: number = Date.now(),
): HomeSignalRow[] {
  const items: AlertEventItem[] = normalizeAlertItems(raw);
  return items
    .map((it) => {
      const family = categorizeSignal(it.signal_type);
      return {
        id: it.id,
        slug: it.market_id,
        family,
        familyLabel: familyLabel(family),
        typeLabel: typeLabel(it.signal_type),
        timeLabel: relativeTime(it.created_at, now),
        createdAt: it.created_at,
        evidence: extractSignalEvidence(it.signal_type, it.payload ?? undefined),
      };
    })
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
}

/** Pure: humanise the top-markets rows (compact volume + YES%). */
export function buildMarketRows(raw: HomeTopMarket[] | null | undefined): HomeMarketRow[] {
  return (Array.isArray(raw) ? raw : [])
    .filter((m): m is HomeTopMarket & { slug: string } => Boolean(m && typeof m.slug === "string" && m.slug))
    .map((m) => ({
      slug: m.slug,
      title: typeof m.title === "string" && m.title.trim() ? m.title : m.slug,
      category: typeof m.category === "string" && m.category.trim() ? m.category : null,
      volumeLabel: isFiniteNum(m.volume) ? VOLUME_FMT.format(m.volume) : "—",
      yesLabel: isFiniteNum(m.yes_price) ? `${Math.round(m.yes_price * 100)}%` : null,
      status: typeof m.status === "string" && m.status.trim() ? m.status : null,
    }));
}

/**
 * Pure transform: raw M01 home aggregate → view model. Reuses the L02 digest,
 * I02/J03 model-A/B, and J02 alert builders so the home page reads exactly like
 * the dedicated surfaces. Honest empties throughout; anon keeps personal
 * sections null/[].
 */
export function buildHomeView(
  raw: HomeResponse | null,
  now: number = Date.now(),
): HomeView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) {
    return {
      reachable: false,
      authenticated: false,
      signals: [],
      digest: buildAlertsDigestView(null, now),
      modelAb: buildModelAbView(null, null),
      topMarkets: [],
      watchlistCount: null,
      watchlistAlerts: [],
      disclaimer,
    };
  }

  const ab = raw.model_ab ?? null;
  const modelAb = buildModelAbView(
    null,
    ab
      ? {
          resolved_count: isFiniteNum(ab.resolved_count) ? ab.resolved_count : 0,
          ab_threshold: isFiniteNum(ab.ab_threshold) ? ab.ab_threshold : 50,
          ab_ready: Boolean(ab.ab_ready),
          model_default: ab.model_default ?? "xgboost",
          paper_trading_only: true,
        }
      : null,
  );

  return {
    reachable: true,
    authenticated: Boolean(raw.authenticated),
    signals: buildSignalRows(raw.signals, now),
    digest: buildAlertsDigestView(raw.digest ?? null, now),
    modelAb,
    topMarkets: buildMarketRows(raw.top_markets),
    watchlistCount: isFiniteNum(raw.watchlist_count) ? raw.watchlist_count : null,
    watchlistAlerts: buildSignalRows(raw.watchlist_alerts, now),
    disclaimer,
  };
}

// ── Network ─────────────────────────────────────────────────────────────────

/**
 * Fetch the personalized home aggregate. PUBLIC GET; sends the JWT session when
 * present so the backend enriches with the watchlist. Returns null with no live
 * API / on a transport error (unreachable); the endpoint itself never 5xxes, so
 * a non-null response with empty sections is an honest empty home.
 */
export async function fetchHome(
  token: string | null,
  opts?: { signalsLimit?: number; marketsLimit?: number; digestWindow?: string; signal?: AbortSignal },
): Promise<HomeResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams();
  if (opts?.signalsLimit) params.set("signals_limit", String(opts.signalsLimit));
  if (opts?.marketsLimit) params.set("markets_limit", String(opts.marketsLimit));
  if (opts?.digestWindow) params.set("digest_window", opts.digestWindow);
  const qs = params.toString();
  try {
    const res = await fetch(apiUrl(`/api/v1/home${qs ? `?${qs}` : ""}`, base), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
      signal: opts?.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as HomeResponse;
  } catch {
    return null;
  }
}
