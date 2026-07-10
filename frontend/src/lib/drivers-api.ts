import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import type { NewsEvidence, SignalEvidence } from "@/lib/signal-evidence";

/**
 * R02: forecast drivers — GET /api/v1/markets/{slug}/drivers (backend N02).
 * "Why does the model think this?" — the model-vs-market gap driver plus recent
 * alert-family signal drivers (each for/against with a family label + citation).
 * READ-ONLY composition; honest {found:false} / empty states, never fabricated.
 */

export type DriverDirection = "favors YES" | "favors NO" | "neutral";

/** H03 citation carried on a signal driver (null for the gap driver). */
export type DriverCitation = {
  signal_id: string;
  news_id: string | null;
  news_url: string | null;
  headline: string | null;
  model_p: number | null;
  market_p: number | null;
};

export type DriverRow = {
  label: string;
  direction: string;
  note: string;
  family: string | null;
  citation: DriverCitation | null;
};

export type DriversResponse = {
  found: boolean;
  slug: string;
  model_p: number | null;
  market_p: number | null;
  gap: number | null;
  drivers: DriverRow[];
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
  generated_at: string;
};

// ---------------------------------------------------------------------------
// View model (pure — unit-tested)
// ---------------------------------------------------------------------------

export type DriverRowView = {
  label: string;
  direction: DriverDirection;
  directionTone: "up" | "down" | "neutral";
  note: string;
  family: string | null;
  evidence: SignalEvidence | null;
};

export type DriversView = {
  found: boolean;
  slug: string;
  /** "62%" or "—". */
  modelLabel: string;
  /** "50%" or "—". */
  marketLabel: string;
  /** Signed gap "+12.0 pts" / "-8.0 pts", or null when either side is missing. */
  gapLabel: string | null;
  gapTone: "up" | "down" | "neutral";
  drivers: DriverRowView[];
  hasDrivers: boolean;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Forecast drivers — signal only; paper trading only, simulated funds, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function pct(v: number | null): string {
  return isFiniteNum(v) ? `${Math.round(v * 100)}%` : "—";
}

function normalizeDirection(raw: string): DriverDirection {
  const v = (raw || "").toLowerCase();
  if (v.includes("yes")) return "favors YES";
  if (v.includes("no")) return "favors NO";
  return "neutral";
}

function directionTone(direction: DriverDirection): "up" | "down" | "neutral" {
  if (direction === "favors YES") return "up";
  if (direction === "favors NO") return "down";
  return "neutral";
}

/** Build renderable news evidence from a driver citation, or null. */
function citationEvidence(citation: DriverCitation | null): NewsEvidence | null {
  if (!citation) return null;
  const headline =
    typeof citation.headline === "string" && citation.headline.trim().length > 0
      ? citation.headline
      : null;
  if (!headline) return null;
  const modelP = isFiniteNum(citation.model_p) ? citation.model_p : null;
  const marketP = isFiniteNum(citation.market_p) ? citation.market_p : null;
  const edge = modelP !== null && marketP !== null ? modelP - marketP : null;
  return {
    kind: "news",
    headline,
    url:
      typeof citation.news_url === "string" && citation.news_url.trim().length > 0
        ? citation.news_url
        : null,
    modelP,
    marketP,
    edgeLabel: edge === null ? null : `${edge >= 0 ? "+" : ""}${(edge * 100).toFixed(1)} pts`,
  };
}

function buildDriverRowView(row: DriverRow): DriverRowView {
  const direction = normalizeDirection(row.direction);
  return {
    label: row.label || "Driver",
    direction,
    directionTone: directionTone(direction),
    note: row.note || "",
    family: typeof row.family === "string" && row.family.length > 0 ? row.family : null,
    evidence: citationEvidence(row.citation),
  };
}

/** Pure transform: raw N02 response → view model. Honest when found=false. */
export function buildDriversView(raw: DriversResponse | null): DriversView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw || !raw.found) {
    return {
      found: false,
      slug: raw?.slug ?? "",
      modelLabel: "—",
      marketLabel: "—",
      gapLabel: null,
      gapTone: "neutral",
      drivers: [],
      hasDrivers: false,
      disclaimer,
    };
  }
  const gap = isFiniteNum(raw.gap) ? raw.gap : null;
  const drivers = (Array.isArray(raw.drivers) ? raw.drivers : []).map(buildDriverRowView);
  return {
    found: true,
    slug: raw.slug,
    modelLabel: pct(raw.model_p),
    marketLabel: pct(raw.market_p),
    gapLabel: gap === null ? null : `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(1)} pts`,
    gapTone: gap === null || Math.abs(gap) < 0.005 ? "neutral" : gap > 0 ? "up" : "down",
    drivers,
    hasDrivers: drivers.length > 0,
    disclaimer,
  };
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

/** Fetch forecast drivers for one market. Returns null with no live API / error. */
export async function fetchDrivers(
  slug: string,
  opts?: { signalsLimit?: number; signal?: AbortSignal },
): Promise<DriversResponse | null> {
  const trimmed = slug.trim();
  if (!trimmed) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams();
  if (opts?.signalsLimit) params.set("signals_limit", String(opts.signalsLimit));
  const qs = params.toString();
  try {
    const res = await fetch(
      `${apiUrl(`/api/v1/markets/${encodeURIComponent(trimmed)}/drivers`, base)}${qs ? `?${qs}` : ""}`,
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as DriversResponse;
  } catch {
    return null;
  }
}
