import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import { marketHref } from "@/lib/market-href";

/**
 * S01/O01: resolved-market review — GET /api/v1/resolved (backend O01). A
 * browsable, READ-ONLY public track record of RESOLVED external markets with the
 * model's prediction vs the real outcome. Computed from REAL resolutions only —
 * never fabricated. Misses count as much as wins: transparency IS the product.
 *
 * CONTRACT (see goals/loop-v10/API-NOTES.md → O01): per-row model-vs-outcome
 * with a per-market Brier, plus a summary header (n, accuracy, mean_brier,
 * thin_data). Honest empty → rows:[], summary n=0.
 */

// ── Raw response (matches API-NOTES.md → O01) ────────────────────────────────

export type ResolvedRow = {
  slug: string;
  title: string;
  resolved_at: string | null;
  outcome: string;
  model_p_at_close: number;
  correct: boolean;
  brier: number;
};

export type ResolvedSummary = {
  n: number;
  accuracy: number | null;
  mean_brier: number | null;
  thin_data: boolean;
  thin_data_threshold: number;
};

export type ResolvedResponse = {
  rows: ResolvedRow[];
  summary: ResolvedSummary;
  count: number;
  limit: number;
  offset: number;
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
  generated_at: string;
  cached: boolean;
};

// ── View model (pure — unit-tested) ──────────────────────────────────────────

export type ResolvedRowView = {
  slug: string;
  title: string;
  href: string;
  resolvedLabel: string | null;
  outcome: "YES" | "NO";
  outcomeTone: "up" | "down";
  /** Model P(YES) at close, e.g. "62%". */
  modelLabel: string;
  correct: boolean;
  /** "Correct" / "Missed" verdict copy. */
  verdictLabel: string;
  verdictTone: "up" | "down";
  /** Per-market Brier, 3-dp, e.g. "0.144". */
  brierLabel: string;
  brier: number;
};

export type ResolvedSummaryView = {
  n: number;
  /** "75%" or "—" at n=0. */
  accuracyLabel: string;
  accuracy: number | null;
  /** Mean Brier, 3-dp, or "—" at n=0. */
  meanBrierLabel: string;
  meanBrier: number | null;
  thinData: boolean;
  threshold: number;
  /** Prominent small-sample caveat when thin_data is true, else null. */
  caveat: string | null;
};

export type ResolvedView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  rows: ResolvedRowView[];
  summary: ResolvedSummaryView;
  disclaimer: string;
  cached: boolean;
};

const FALLBACK_DISCLAIMER =
  "Resolved-market review — a read-only public track record from REAL resolutions only. Misses count as much as wins. Paper trading only, simulated funds, no execution.";

function isFiniteNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function brierText(v: number | null): string {
  return isFiniteNum(v) ? v.toFixed(3) : "—";
}

function buildRowView(row: ResolvedRow): ResolvedRowView {
  const outcome: "YES" | "NO" = row.outcome === "YES" ? "YES" : "NO";
  const correct = row.correct === true;
  return {
    slug: row.slug,
    title: row.title || row.slug,
    href: marketHref(row.slug),
    resolvedLabel: row.resolved_at
      ? new Date(row.resolved_at).toLocaleDateString()
      : null,
    outcome,
    outcomeTone: outcome === "YES" ? "up" : "down",
    modelLabel: isFiniteNum(row.model_p_at_close) ? pct(row.model_p_at_close) : "—",
    correct,
    verdictLabel: correct ? "Correct" : "Missed",
    verdictTone: correct ? "up" : "down",
    brierLabel: brierText(isFiniteNum(row.brier) ? row.brier : null),
    brier: isFiniteNum(row.brier) ? row.brier : 0,
  };
}

function buildSummaryView(summary: ResolvedSummary | null | undefined): ResolvedSummaryView {
  const n = isFiniteNum(summary?.n) ? (summary!.n as number) : 0;
  const accuracy = isFiniteNum(summary?.accuracy) ? (summary!.accuracy as number) : null;
  const meanBrier = isFiniteNum(summary?.mean_brier) ? (summary!.mean_brier as number) : null;
  const threshold = isFiniteNum(summary?.thin_data_threshold)
    ? (summary!.thin_data_threshold as number)
    : 30;
  const thinData = summary?.thin_data === true;
  return {
    n,
    accuracyLabel: accuracy === null ? "—" : pct(accuracy),
    accuracy,
    meanBrierLabel: brierText(meanBrier),
    meanBrier,
    thinData,
    threshold,
    caveat:
      thinData && n > 0
        ? `Small sample (n=${n}) — fewer than ${threshold} resolved markets. Treat accuracy and Brier as provisional, not proven.`
        : null,
  };
}

/**
 * Pure transform: raw O01 response → view model. Honest unreachable / empty
 * states; nothing is fabricated. `buildResolvedView(null)` marks the page
 * unreachable; an empty-but-reachable page reports n=0 honestly.
 */
export function buildResolvedView(raw: ResolvedResponse | null): ResolvedView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) {
    return {
      reachable: false,
      rows: [],
      summary: buildSummaryView(null),
      disclaimer,
      cached: false,
    };
  }
  const rowsRaw = Array.isArray(raw.rows) ? raw.rows : [];
  return {
    reachable: true,
    rows: rowsRaw.map(buildRowView),
    summary: buildSummaryView(raw.summary),
    disclaimer,
    cached: raw.cached === true,
  };
}

// ── Network (reuses the shared alphaedge-api base resolver; no poll loop) ─────

/**
 * Fetch one page of the resolved-market review. PUBLIC GET (no auth). Returns
 * null with no live API / on a transport error (unreachable). Bounded
 * pagination via `limit` (1..200) + `offset` (>=0).
 */
export async function fetchResolved(
  opts?: { limit?: number; offset?: number; signal?: AbortSignal },
): Promise<ResolvedResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams();
  params.set("limit", String(opts?.limit ?? 50));
  params.set("offset", String(opts?.offset ?? 0));
  try {
    const res = await fetch(
      `${apiUrl("/api/v1/resolved", base)}?${params.toString()}`,
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as ResolvedResponse;
  } catch {
    return null;
  }
}
