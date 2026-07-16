import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "./alphaedge-api";
import { relativeTime } from "./alerts-api";

/**
 * F1/F2 (loop47): public LIVE ForecastLog lock chip.
 * GET /api/v1/markets/{slug}/locked-forecast
 *
 * Never fabricates a probability — only surfaces API fields. Pre-lock and
 * unreachable API are honest empty states.
 */

export type LockedForecastResponse = {
  slug: string;
  locked: boolean;
  user_probability: number | null;
  locked_at: string | null;
  market_implied_at_lock: number | null;
  current_market_probability: number | null;
  mode: string | null;
  provisional: boolean;
  paper_trading_only: boolean;
  forecast_id: string | null;
  external_market_id: string | null;
  empty_reason: string | null;
};

export type LockedForecastViewState = "loading" | "unavailable" | "pre_lock" | "locked";

export type LockedForecastView = {
  state: LockedForecastViewState;
  /** Locked model % label, e.g. "62%". Null when not locked. */
  lockedProbLabel: string | null;
  /** Relative lock age, e.g. "2h ago". Null when not locked / unparseable. */
  lockedAtRelative: string | null;
  /** Current market YES % label. Null when API omitted current price. */
  currentProbLabel: string | null;
  /** Signed pts delta: locked − current. Null when either side missing. */
  deltaPts: number | null;
  deltaLabel: string | null;
  provisional: boolean;
  paperTradingOnly: boolean;
  emptyCopy: string | null;
};

const PRE_LOCK_COPY = "Model forecast locks near close";
const UNAVAILABLE_COPY = "Locked forecast unavailable — API not reachable. Nothing fabricated.";

function num(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function pctLabel(p: number | null): string | null {
  if (p === null) return null;
  return `${Math.round(p * 100)}%`;
}

function deltaPts(locked: number | null, current: number | null): number | null {
  if (locked === null || current === null) return null;
  return Math.round((locked - current) * 100);
}

function deltaLabel(pts: number | null): string | null {
  if (pts === null) return null;
  if (pts === 0) return "0 pts vs market";
  return pts > 0 ? `+${pts} pts vs market` : `${pts} pts vs market`;
}

/** Pure view-model — never invents a probability from mock or XGBoost fields. */
export function buildLockedForecastView(
  raw: LockedForecastResponse | null,
  opts: { loading?: boolean; nowMs?: number } = {},
): LockedForecastView {
  if (opts.loading) {
    return {
      state: "loading",
      lockedProbLabel: null,
      lockedAtRelative: null,
      currentProbLabel: null,
      deltaPts: null,
      deltaLabel: null,
      provisional: true,
      paperTradingOnly: true,
      emptyCopy: null,
    };
  }

  if (!raw) {
    return {
      state: "unavailable",
      lockedProbLabel: null,
      lockedAtRelative: null,
      currentProbLabel: null,
      deltaPts: null,
      deltaLabel: null,
      provisional: true,
      paperTradingOnly: true,
      emptyCopy: UNAVAILABLE_COPY,
    };
  }

  const userProb = num(raw.user_probability);
  const currentProb = num(raw.current_market_probability);
  const provisional = Boolean(raw.provisional);
  const paperTradingOnly = raw.paper_trading_only !== false;

  // Honest empty: unlocked OR locked flag with null probability (never invent %).
  if (!raw.locked || userProb === null) {
    return {
      state: "pre_lock",
      lockedProbLabel: null,
      lockedAtRelative: null,
      currentProbLabel: pctLabel(currentProb),
      deltaPts: null,
      deltaLabel: null,
      provisional,
      paperTradingOnly,
      emptyCopy: PRE_LOCK_COPY,
    };
  }

  const pts = deltaPts(userProb, currentProb);
  const lockedAt =
    typeof raw.locked_at === "string" && raw.locked_at.trim()
      ? relativeTime(raw.locked_at, opts.nowMs ?? Date.now())
      : null;

  return {
    state: "locked",
    lockedProbLabel: pctLabel(userProb),
    lockedAtRelative: lockedAt || null,
    currentProbLabel: pctLabel(currentProb),
    deltaPts: pts,
    deltaLabel: deltaLabel(pts),
    provisional,
    paperTradingOnly,
    emptyCopy: null,
  };
}

export async function fetchLockedForecast(
  slug: string,
): Promise<LockedForecastResponse | null> {
  const trimmed = slug.trim();
  if (!trimmed) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const res = await fetch(
      apiUrl(`/api/v1/markets/${encodeURIComponent(trimmed)}/locked-forecast`, base),
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as LockedForecastResponse;
  } catch {
    return null;
  }
}

export { PRE_LOCK_COPY, UNAVAILABLE_COPY };
