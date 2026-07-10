import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import {
  buildShareSnapshotView,
  type ShareEdge,
  type ShareSnapshotResponse,
  type ShareSnapshotView,
  type ShareTopSignal,
} from "@/lib/share-snapshot-api";

/**
 * S03/O03: market comparison — GET /api/v1/compare?slugs=a,b[,c,d] (backend
 * O03). Side-by-side compact intelligence for 2-4 markets. Each entry is the
 * M02 share-snapshot core shape, so each compare COLUMN reuses
 * `buildShareSnapshotView` — the columns and the /s/[slug] share card never
 * diverge. Unknown slug degrades to an honest per-column {found:false} (never a
 * 404). Read-only analysis; NOT an order feed.
 *
 * CONTRACT: see goals/loop-v10/API-NOTES.md → O03.
 */

// ── Raw response (matches API-NOTES.md → O03) ────────────────────────────────

export type CompareEntry = {
  found?: boolean;
  slug?: string;
  title?: string | null;
  yes_price?: number | null;
  edge?: ShareEdge | null;
  top_signal?: ShareTopSignal | null;
  arb_matched?: boolean;
  smart_money_note?: string | null;
};

export type CompareResponse = {
  entries: CompareEntry[];
  count: number;
  requested: string[];
  clamped: boolean;
  max_slugs: number;
  paper_trading_only?: boolean;
  signal_only?: boolean;
  disclaimer?: string;
  generated_at?: string;
};

// ── View model (pure — unit-tested) ──────────────────────────────────────────

/** One compare column: the share-snapshot view plus its requested slug. */
export type CompareColumnView = ShareSnapshotView & {
  requestedSlug: string;
  /** Raw YES price (0..1) for AnimatedNumber, or null when none. */
  yesPrice: number | null;
};

export type CompareView = {
  /** False when the API is unreachable (null response). */
  reachable: boolean;
  columns: CompareColumnView[];
  requested: string[];
  /** True when >max_slugs were requested and the tail was dropped. */
  clamped: boolean;
  maxSlugs: number;
  disclaimer: string;
};

const FALLBACK_DISCLAIMER =
  "Market comparison — a read-only side-by-side of the desk's intelligence for each market. Paper trading only, simulated funds, no execution. NOT an order feed.";

const MAX_SLUGS = 4;

/**
 * Parse a comma-separated slug string into a bounded, de-duplicated list
 * (blanks dropped, order preserved, clamped to `MAX_SLUGS`). Mirrors the
 * backend O03 parse so the URL the picker builds matches what the server does.
 */
export function parseCompareSlugs(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const slug = part.trim();
    if (!slug || out.includes(slug)) continue;
    out.push(slug);
    if (out.length >= MAX_SLUGS) break;
  }
  return out;
}

/** Map a compare entry to the share-snapshot response shape (identical core). */
function entryToSnapshot(entry: CompareEntry): ShareSnapshotResponse {
  return {
    found: entry.found,
    slug: entry.slug,
    title: entry.title ?? null,
    yes_price: entry.yes_price ?? null,
    edge: entry.edge ?? null,
    top_signal: entry.top_signal ?? null,
    arb_matched: entry.arb_matched,
    smart_money_note: entry.smart_money_note ?? null,
  };
}

/**
 * Pure transform: raw O03 response → view model. Each column reuses the M02
 * share-snapshot view builder. Honest unreachable / per-column not-found;
 * nothing is fabricated.
 */
export function buildCompareView(
  raw: CompareResponse | null,
  now: number = Date.now(),
): CompareView {
  const disclaimer = raw?.disclaimer || FALLBACK_DISCLAIMER;
  if (!raw) {
    return {
      reachable: false,
      columns: [],
      requested: [],
      clamped: false,
      maxSlugs: MAX_SLUGS,
      disclaimer,
    };
  }
  const entries = Array.isArray(raw.entries) ? raw.entries : [];
  const columns: CompareColumnView[] = entries.map((entry) => {
    const view = buildShareSnapshotView(entryToSnapshot(entry), now);
    return {
      ...view,
      requestedSlug: typeof entry.slug === "string" ? entry.slug : view.slug,
      yesPrice:
        typeof entry.yes_price === "number" && Number.isFinite(entry.yes_price)
          ? entry.yes_price
          : null,
    };
  });
  return {
    reachable: true,
    columns,
    requested: Array.isArray(raw.requested) ? raw.requested : [],
    clamped: raw.clamped === true,
    maxSlugs: typeof raw.max_slugs === "number" ? raw.max_slugs : MAX_SLUGS,
    disclaimer,
  };
}

// ── Network (reuses the shared alphaedge-api base resolver; no poll loop) ─────

/**
 * Fetch the side-by-side comparison for a set of slugs. PUBLIC GET (no auth).
 * Returns null with no live API / on a transport error (unreachable). No slugs
 * → honest empty {entries:[]}; the endpoint never 5xxes on unknown slugs.
 */
export async function fetchCompare(
  slugs: string[],
  opts?: { signal?: AbortSignal },
): Promise<CompareResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams();
  if (slugs.length > 0) params.set("slugs", slugs.join(","));
  try {
    const res = await fetch(
      `${apiUrl("/api/v1/compare", base)}?${params.toString()}`,
      { cache: "no-store", signal: opts?.signal },
    );
    if (!res.ok) return null;
    return (await res.json()) as CompareResponse;
  } catch {
    return null;
  }
}
