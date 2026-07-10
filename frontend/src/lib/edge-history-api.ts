import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * R03: edge history — GET /api/v1/markets/{slug}/edge-history (backend N03). A
 * bounded time series of model_p vs market_p for charting the model-vs-market
 * edge over time. READ-ONLY; honest empty states.
 *
 * CONTRACT NOTE (see goals/loop-v9/API-NOTES.md): each point's `edge` here is
 * the SIGNED gap `model_p − market_p` (shows which side the model leaned and
 * when it flipped) — NOT the absolute rank key from the N01 scanner.
 */

export type EdgeHistoryPoint = {
  t: string;
  model_p: number;
  market_p: number | null;
  edge: number | null;
};

export type EdgeHistoryResponse = {
  found: boolean;
  slug: string;
  window: string;
  window_hours: number;
  series: EdgeHistoryPoint[];
  count: number;
  max_points: number;
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
  generated_at: string;
  cached: boolean;
};

// ---------------------------------------------------------------------------
// View model (pure — unit-tested)
// ---------------------------------------------------------------------------

export type EdgePointView = {
  t: string;
  modelP: number;
  marketP: number | null;
  /** SIGNED edge model_p − market_p; null when market_p is missing. */
  edge: number | null;
};

export type EdgeHistoryView = {
  found: boolean;
  slug: string;
  /** True only with ≥2 model points — a single dot is not a "trend" line. */
  available: boolean;
  points: EdgePointView[];
  /** True when at least one point has a market_p (draw the market line). */
  hasMarketLine: boolean;
  /** Latest point's labels, or null when there are no points. */
  latest: {
    modelLabel: string;
    marketLabel: string;
    edgeLabel: string | null;
    edgeTone: "up" | "down" | "neutral";
  } | null;
  count: number;
  windowLabel: string;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Model-vs-market edge history — signal only; paper trading only, simulated funds, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function pct(v: number | null): string {
  return isFiniteNum(v) ? `${Math.round(v * 100)}%` : "—";
}

function signedPts(v: number | null): string | null {
  return isFiniteNum(v) ? `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)} pts` : null;
}

/** Pure transform: raw N03 response → chart view model. Honest when empty. */
export function buildEdgeHistoryView(raw: EdgeHistoryResponse | null): EdgeHistoryView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  const windowLabel = raw?.window || "7d";
  if (!raw || !raw.found) {
    return {
      found: false,
      slug: raw?.slug ?? "",
      available: false,
      points: [],
      hasMarketLine: false,
      latest: null,
      count: 0,
      windowLabel,
      disclaimer,
    };
  }
  const points: EdgePointView[] = (Array.isArray(raw.series) ? raw.series : [])
    .filter((p) => isFiniteNum(p.model_p))
    .map((p) => {
      const marketP = isFiniteNum(p.market_p) ? p.market_p : null;
      const edge = isFiniteNum(p.edge)
        ? p.edge
        : marketP !== null
          ? p.model_p - marketP
          : null;
      return { t: p.t, modelP: p.model_p, marketP, edge };
    });
  const last = points[points.length - 1] ?? null;
  const latest = last
    ? {
        modelLabel: pct(last.modelP),
        marketLabel: pct(last.marketP),
        edgeLabel: signedPts(last.edge),
        edgeTone: (last.edge === null || Math.abs(last.edge) < 0.005
          ? "neutral"
          : last.edge > 0
            ? "up"
            : "down") as "up" | "down" | "neutral",
      }
    : null;
  return {
    found: true,
    slug: raw.slug,
    available: points.length >= 2,
    points,
    hasMarketLine: points.some((p) => p.marketP !== null),
    latest,
    count: points.length,
    windowLabel,
    disclaimer,
  };
}

/**
 * Pure SVG path builder for a probability line (y-domain fixed to 0..1 so the
 * model and market lines are directly comparable). `null` values break the line
 * (a new sub-path starts after the gap). Returns "" when nothing is drawable.
 */
export function buildLinePath(
  values: (number | null)[],
  dims: { width: number; height: number; pad: number },
): string {
  const { width, height, pad } = dims;
  const n = values.length;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const x = (i: number) => pad + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => pad + (1 - Math.max(0, Math.min(1, v))) * innerH;
  let d = "";
  let penDown = false;
  for (let i = 0; i < n; i++) {
    const v = values[i];
    if (v === null || !Number.isFinite(v)) {
      penDown = false;
      continue;
    }
    d += `${penDown ? "L" : "M"}${x(i).toFixed(2)},${y(v).toFixed(2)}`;
    penDown = true;
  }
  return d;
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

/** Fetch the edge history series for one market. Null with no live API / error. */
export async function fetchEdgeHistory(
  slug: string,
  opts?: { window?: string; signal?: AbortSignal },
): Promise<EdgeHistoryResponse | null> {
  const trimmed = slug.trim();
  if (!trimmed) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams();
  if (opts?.window) params.set("window", opts.window);
  const qs = params.toString();
  try {
    const res = await fetch(
      `${apiUrl(`/api/v1/markets/${encodeURIComponent(trimmed)}/edge-history`, base)}${qs ? `?${qs}` : ""}`,
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as EdgeHistoryResponse;
  } catch {
    return null;
  }
}
