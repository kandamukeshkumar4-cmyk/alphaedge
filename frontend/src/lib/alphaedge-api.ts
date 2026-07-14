import { apiCatalogToMarkets, type ApiMarketCatalogItem } from "./api-market-adapter";
import { mergeApiSnapshotForDetail } from "./api-market-detail-adapter";
import { MARKETS, type Market as CardMarket } from "./mock-data";
import type { Market, MarketSnapshot } from "./market-view-model";

// Resolve the backend the deployed site talks to.
//
// Production browser: empty base = same-origin Vercel rewrite → HF Space
// (see next.config.ts). HF free-tier often returns CORS-less 429 HTML; a
// cross-origin fetch then looks like a hard outage (health down, markets
// refresh fail, ATLAS "Could not reach"). Same-origin keeps status readable.
//
// Production SSR / Node: absolute HF URL (rewrites are browser-facing).
// Dev without NEXT_PUBLIC_API_URL: probe localhost:8000/health once; if the
// local API is down, fall back to the HF Space prod URL.
const HF_PROD_API = "https://mukeshkumar007-alphaedge-api.hf.space";
const LOCAL_DEV_API = "http://localhost:8000";
/** Empty string — browser production uses Vercel /api + /health rewrites. */
const SAME_ORIGIN = "";

function readEnvApiUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "");
}

function isHfSpaceUrl(url: string): boolean {
  return /(?:^|\.)hf\.space$/i.test(url.replace(/^https?:\/\//, "").split("/")[0] ?? "");
}

/** Browser prod should not call HF cross-origin (CORS-less 429 HTML). */
function browserProdBase(env: string): string {
  if (!env || isHfSpaceUrl(env)) return SAME_ORIGIN;
  return env;
}

function syncDefaultBase(): string {
  const env = readEnvApiUrl();
  if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
    return browserProdBase(env);
  }
  if (env) return env;
  if (process.env.NODE_ENV === "production") return HF_PROD_API;
  return LOCAL_DEV_API;
}

let _resolvedBase: string | null = null;
let _probePromise: Promise<string> | null = null;

export async function resolveApiBase(): Promise<string> {
  const env = readEnvApiUrl();
  if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
    _resolvedBase = browserProdBase(env);
    return _resolvedBase;
  }
  if (env) {
    _resolvedBase = env;
    return env;
  }
  if (process.env.NODE_ENV === "production") {
    _resolvedBase = HF_PROD_API;
    return HF_PROD_API;
  }
  if (_resolvedBase !== null) return _resolvedBase;
  if (_probePromise) return _probePromise;

  _probePromise = (async () => {
    try {
      const response = await fetch(`${LOCAL_DEV_API}/health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(2500),
      });
      _resolvedBase = response.ok ? LOCAL_DEV_API : HF_PROD_API;
    } catch {
      _resolvedBase = HF_PROD_API;
    }
    _probePromise = null;
    return _resolvedBase!;
  })();

  return _probePromise;
}

/** Live binding — updated after {@link ensureApiBase} in dev when local API is down. */
export let API_BASE = syncDefaultBase();

export let WS_BASE =
  (process.env.NEXT_PUBLIC_WS_URL || "").trim() ||
  (API_BASE ? API_BASE.replace(/^http/, "ws") : "");

/** True when live API calls should run (incl. same-origin proxy with API_BASE=""). */
export function hasLiveApi(base: string = API_BASE): boolean {
  if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
    return true;
  }
  if (readEnvApiUrl()) return true;
  if (process.env.NODE_ENV === "production") return true;
  return Boolean(base);
}

/** Join API_BASE + path. Empty base → same-origin `/api/...`. */
export function apiUrl(path: string, base: string = API_BASE): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (!base) return p;
  return `${base.replace(/\/+$/, "")}${p}`;
}

export async function ensureApiBase(): Promise<string> {
  const base = await resolveApiBase();
  API_BASE = base;
  WS_BASE =
    (process.env.NEXT_PUBLIC_WS_URL || "").trim() ||
    (base ? base.replace(/^http/, "ws") : "");
  return base;
}
export const PAPER_BALANCE = 100_000;
export const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

/**
 * FastAPI may return `detail` as a string or as a validation-error array/object.
 * Never pass the raw value into React children — that throws React error #31.
 */
export function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const msg = (item as { msg?: unknown }).msg;
          return typeof msg === "string" ? msg : null;
        }
        return null;
      })
      .filter((part): part is string => Boolean(part));
    if (parts.length > 0) return parts.join("; ");
  }
  if (detail && typeof detail === "object" && "msg" in detail) {
    const msg = (detail as { msg?: unknown }).msg;
    if (typeof msg === "string" && msg.trim()) return msg;
  }
  return fallback;
}

export type Candle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type HistoryPoint = {
  timestamp: number;
  yes_price: number;
};

export async function fetchMarketHistory(
  slug: string,
  days = 7,
): Promise<HistoryPoint[]> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return [];
  try {
    const response = await fetch(
      apiUrl(
        `/api/v1/markets/${encodeURIComponent(slug)}/history?days=${days}`,
        base,
      ),
      { cache: "no-store" },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { history?: HistoryPoint[] };
    return data.history ?? [];
  } catch {
    return [];
  }
}

export type OrderBookLevel = { price: number; size: number };
export type OrderBookSide = { bids: OrderBookLevel[]; asks: OrderBookLevel[] };
export type OrderBookResponse = { yes: OrderBookSide; no: OrderBookSide };

export async function fetchOrderBook(slug: string): Promise<OrderBookResponse | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const response = await fetch(
      apiUrl(`/api/v1/markets/${encodeURIComponent(slug)}/book`, base),
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    return (await response.json()) as OrderBookResponse;
  } catch {
    return null;
  }
}

export type LivePrice = {
  slug: string;
  yes: number;
  no: number;
  ts: string | null;
  source: "db" | "seed";
};

export async function fetchLatestPrice(slug: string): Promise<LivePrice | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return null;
  }

  try {
    const response = await fetch(
      apiUrl(`/api/v1/markets/${encodeURIComponent(slug)}/prices/latest`, base),
      { cache: "no-store" },
    );
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as LivePrice;
  } catch {
    return null;
  }
}

// loop6 — agent-memory feed (loop3). Read-only "what the system learned":
// recently remembered resolved markets with the model-vs-market outcome + Brier.
export type AgentMemoryRow = {
  id: string;
  market_slug: string;
  category: string;
  question: string;
  outcome: string;
  model_prob_at_close: number | null;
  market_prob_at_close: number | null;
  brier: number | null;
  rationale_summary: string;
  created_at: string;
};

export async function fetchMemories(
  category?: string,
  limit = 8,
): Promise<AgentMemoryRow[]> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return [];
  }
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  params.set("limit", String(limit));
  try {
    const response = await fetch(
      apiUrl(`/api/v1/memories?${params.toString()}`, base),
      { cache: "no-store" },
    );
    if (!response.ok) {
      return [];
    }
    const data = (await response.json()) as { items?: AgentMemoryRow[]; total?: number };
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

export async function fetchMarketCandles(
  slug: string,
  points = 90,
): Promise<Candle[] | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return null;
  }

  try {
    const response = await fetch(
      apiUrl(
        `/api/v1/markets/${encodeURIComponent(slug)}/candles?points=${points}`,
        base,
      ),
      { cache: "no-store" },
    );
    if (!response.ok) {
      return null;
    }
    const data = (await response.json()) as { candles?: Candle[]; source?: string };
    return data.candles ?? null;
  } catch {
    return null;
  }
}

export async function fetchMarketCandlesMeta(
  slug: string,
  points = 90,
): Promise<{ candles: Candle[]; source: string } | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  try {
    const response = await fetch(
      apiUrl(
        `/api/v1/markets/${encodeURIComponent(slug)}/candles?points=${points}`,
        base,
      ),
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    const data = (await response.json()) as { candles?: Candle[]; source?: string };
    return { candles: data.candles ?? [], source: data.source ?? "unknown" };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// U10 — Backtest replay API
// ---------------------------------------------------------------------------

export type EquityPoint = { timestamp: string; equity: number };
export type FillQualityStats = {
  trade_count: number;
  mean_slippage: number;
  max_slippage: number;
  total_realized_pnl: number;
  mean_realized_pnl: number;
};
export type BrierPoint = { timestamp: string; brier: number; sample_count: number };

export type BacktestRunResult = {
  id: string;
  market_slug: string;
  clone_id: string | null;
  start_date: string;
  end_date: string;
  initial_equity: number;
  final_equity: number | null;
  equity_curve: EquityPoint[];
  fill_quality: FillQualityStats | null;
  brier_over_time: BrierPoint[];
  brier_final: number | null;
  snapshot_count: number;
  trade_count: number;
  no_lookahead_verified: boolean;
  insufficient_data: boolean;
  status: string;
  paper_trading_only: boolean;
  created_at: string;
};

export type BacktestRunRequest = {
  market_slug: string;
  start_date: string;
  end_date: string;
  initial_equity?: number;
  stake?: number;
  spread?: number;
  slippage_per_unit?: number;
  edge_threshold?: number;
  clone_id?: string;
};

export async function triggerBacktestRun(
  req: BacktestRunRequest,
  token: string,
): Promise<BacktestRunResult | null> {
  if (!API_BASE) return null;
  try {
    const response = await fetch(`${API_BASE}/api/v1/backtest/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(req),
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as BacktestRunResult;
  } catch {
    return null;
  }
}

export async function fetchBacktestRuns(
  market_slug?: string,
  limit = 20,
): Promise<BacktestRunResult[]> {
  if (!API_BASE) return [];
  try {
    const params = new URLSearchParams({ limit: String(limit) });
    if (market_slug) params.set("market_slug", market_slug);
    const response = await fetch(`${API_BASE}/api/v1/backtest/runs?${params}`, {
      cache: "no-store",
    });
    if (!response.ok) return [];
    return (await response.json()) as BacktestRunResult[];
  } catch {
    return [];
  }
}

export async function fetchBacktestRun(runId: string): Promise<BacktestRunResult | null> {
  if (!API_BASE) return null;
  try {
    const response = await fetch(`${API_BASE}/api/v1/backtest/runs/${encodeURIComponent(runId)}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as BacktestRunResult;
  } catch {
    return null;
  }
}

export const canonicalMarket: Market = {
  id: "00000000-0000-0000-0000-000000000101",
  slug: CANONICAL_SLUG,
  title: "Lakers vs Celtics",
  question: "Will the Lakers win?",
  category: "Sports",
  icon: "🏀",
  volume: 2_413_000,
  traders: 3_214,
  market_count: 3,
  description: "Head-to-head paper market on the Lakers vs Celtics matchup.",
  resolution: "Resolves YES if the Lakers win the game, otherwise NO.",
  status: "open",
  lock_at: "2025-01-15T19:30:00Z",
  resolved_at: null,
  winning_outcome: null,
};

export const fallbackSnapshot: MarketSnapshot = {
  paper_trading_only: true,
  disclaimer:
    "This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only.",
  market: canonicalMarket,
  book: {
    yes: {
      bids: [
        { price: 0.63, size: 1240 },
        { price: 0.62, size: 830 },
        { price: 0.61, size: 520 },
      ],
      asks: [
        { price: 0.64, size: 980 },
        { price: 0.65, size: 730 },
        { price: 0.66, size: 410 },
      ],
    },
    no: {
      bids: [
        { price: 0.35, size: 760 },
        { price: 0.34, size: 520 },
        { price: 0.33, size: 480 },
      ],
      asks: [
        { price: 0.36, size: 910 },
        { price: 0.37, size: 640 },
        { price: 0.38, size: 390 },
      ],
    },
  },
  activity: [
    {
      id: "00000000-0000-0000-0000-000000000201",
      outcome: "yes",
      price: 0.64,
      quantity: 25,
      created_at: "2026-06-02T17:00:00Z",
    },
    {
      id: "00000000-0000-0000-0000-000000000202",
      outcome: "no",
      price: 0.36,
      quantity: 14,
      created_at: "2026-06-02T16:56:00Z",
    },
  ],
  forecast: {
    predicted_prob: 0.68,
    confidence: 0.84,
    edge_vs_book: 0.04,
    input_feature_hash: "fixture-v1",
  },
  evaluation: {
    latest_brier_score: 0.1024,
    predicted_prob: 0.68,
    actual_outcome: 1,
    closing_implied: 0.64,
  },
};

export type MarketFilterParams = {
  category?: string;
  sort?: "volume" | "traders" | "newest" | "active";
  q?: string;
};

/** Map UI/backend category labels to valid GET /markets category query values. */
export function toApiCategory(category: string): string | undefined {
  const normalized = category.trim().toLowerCase();
  const map: Record<string, string> = {
    sports: "sports",
    nba: "sports",
    "fifa wc2026": "sports",
    politics: "politics",
    elections: "politics",
    crypto: "crypto",
    culture: "culture",
    economics: "economics",
  };
  return map[normalized];
}

// Shared client cache for market catalog fetches. Many surfaces (signal rail,
// live ticker, discover, markets board, trade terminal, similar markets) poll
// the same GET /markets; without coalescing the homepage alone can fire 5+
// identical requests per cycle and trip SlowAPI 429s on the free-tier API.
const MARKETS_CACHE_TTL_MS = 4000;
type MarketsCacheEntry = { promise: Promise<CardMarket[]>; expiresAt: number };
const marketsCache = new Map<string, MarketsCacheEntry>();

function marketsCacheKey(params?: MarketFilterParams): string {
  return [params?.category ?? "", params?.sort ?? "", params?.q ?? ""].join("|");
}

/** Test hook: reset the shared markets cache. */
export function __clearMarketsCache(): void {
  marketsCache.clear();
}

export async function fetchMarkets(params?: MarketFilterParams): Promise<CardMarket[]> {
  const key = marketsCacheKey(params);
  const now = Date.now();
  const cached = marketsCache.get(key);
  if (cached && cached.expiresAt > now) {
    return cached.promise;
  }
  const promise = fetchMarketsUncached(params);
  marketsCache.set(key, { promise, expiresAt: now + MARKETS_CACHE_TTL_MS });
  // Never cache failures — the next caller should retry the network.
  promise.catch(() => {
    if (marketsCache.get(key)?.promise === promise) {
      marketsCache.delete(key);
    }
  });
  return promise;
}

async function fetchMarketsUncached(params?: MarketFilterParams): Promise<CardMarket[]> {
  const apiBase = await ensureApiBase();
  if (!hasLiveApi(apiBase)) {
    return [];
  }

  const origin =
    apiBase ||
    (typeof window !== "undefined" ? window.location.origin : HF_PROD_API);
  const url = new URL(apiUrl("/api/v1/markets", apiBase), origin);
  if (params?.category && params.category !== "all") {
    const apiCategory = toApiCategory(params.category);
    if (apiCategory) {
      url.searchParams.set("category", apiCategory);
    }
  }
  if (params?.sort) url.searchParams.set("sort", params.sort);
  if (params?.q) url.searchParams.set("q", params.q);

  // Relative fetch when same-origin proxy is active (keeps cookies/origin clean).
  const href = apiBase ? url.toString() : `${url.pathname}${url.search}`;
  const response = await fetch(href, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Markets HTTP ${response.status}`);
  }
  const markets = (await response.json()) as ApiMarketCatalogItem[];
  return apiCatalogToMarkets(markets);
}

export type PatchMeRequest = {
  onboarded?: boolean;
  display_name?: string;
};

export type PatchMeResponse = {
  onboarded: boolean;
  display_name: string | null;
};

export async function patchMe(
  token: string,
  body: PatchMeRequest,
): Promise<PatchMeResponse | null> {
  if (!API_BASE) return null;
  try {
    const resp = await fetch(`${API_BASE}/api/v1/auth/me`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok) return null;
    return (await resp.json()) as PatchMeResponse;
  } catch {
    return null;
  }
}

export async function fetchMarketSnapshot(slug: string): Promise<MarketSnapshot> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return fallbackForSlug(slug);
  }

  try {
    const response = await fetch(
      apiUrl(`/api/v1/markets/${slug}/snapshot`, base),
      { cache: "no-store" },
    );
    if (!response.ok) {
      return fallbackForSlug(slug);
    }
    return (await response.json()) as MarketSnapshot;
  } catch {
    return fallbackForSlug(slug);
  }
}

export type MarketDetailApi = {
  slug: string;
  title: string;
  category: string;
  status: string;
  outcomes: Array<{ label: string; implied_prob: number; price: number }>;
  forecast: {
    model_prob: number;
    clv_gate_passed: boolean;
    provisional: boolean;
    // loop6 — optional ensemble + tool fields (present only on newer backends).
    n_models?: number;
    stdev?: number;
    spread_flag?: boolean;
    per_model?: Array<{ provider: string; prob: number; rationale: string }>;
    tools_used?: string[];
  } | null;
  volume_usd: number;
  traders: number;
  resolution_criteria: string;
  paper_trading_only: boolean;
  resolved: boolean;
  resolution_outcome: "YES" | "NO" | "VOID" | null;
  winning_outcome?: "YES" | "NO" | "VOID" | null;
  resolved_at?: string | null;
};

export async function fetchMarketDetailApi(
  slug: string,
): Promise<MarketDetailApi | null> {
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return null;
  }

  try {
    const response = await fetch(
      apiUrl(`/api/v1/markets/${slug}/detail`, base),
      { cache: "no-store" },
    );
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as MarketDetailApi;
  } catch {
    return null;
  }
}

export async function fetchMarketDetail(slug: string): Promise<CardMarket | null> {
  const detail = await fetchMarketDetailApi(slug);
  if (detail) {
    return mergeApiDetailForCards(detail, MARKETS);
  }

  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) {
    return null;
  }

  try {
    const snapshot = await fetchMarketSnapshot(slug);
    return mergeApiSnapshotForDetail(snapshot, MARKETS);
  } catch {
    return null;
  }
}

function mergeApiDetailForCards(
  detail: MarketDetailApi,
  localMarkets: CardMarket[],
): CardMarket {
  const local = localMarkets.find((market) => market.slug === detail.slug);
  const yes = detail.outcomes.find((outcome) => outcome.label === "YES");
  const no = detail.outcomes.find((outcome) => outcome.label === "NO");
  const yesPrice = yes?.price ?? 0.5;
  const noPrice = no?.price ?? 0.5;

  return {
    id: local?.id ?? detail.slug,
    slug: detail.slug,
    category: (detail.category as CardMarket["category"]) ?? local?.category ?? "Sports",
    icon: local?.icon ?? "📊",
    title: detail.title,
    question: local?.question ?? detail.title,
    endsAt: local?.endsAt ?? new Date().toISOString(),
    volume: detail.volume_usd,
    traders: detail.traders,
    marketCount: local?.marketCount ?? 1,
    trendDelta: local?.trendDelta ?? 0,
    outcomes: [
      {
        id: "yes",
        label: local?.outcomes[0]?.label ?? "YES",
        emoji: local?.outcomes[0]?.emoji ?? "Y",
        price: yesPrice,
        prevPrice: local?.outcomes[0]?.prevPrice ?? yesPrice,
        tone: local?.outcomes[0]?.tone ?? "primary",
      },
      {
        id: "no",
        label: local?.outcomes[1]?.label ?? "NO",
        emoji: local?.outcomes[1]?.emoji ?? "N",
        price: noPrice,
        prevPrice: local?.outcomes[1]?.prevPrice ?? noPrice,
        tone: local?.outcomes[1]?.tone ?? "danger",
      },
      ...(local?.outcomes.slice(2) ?? []),
    ],
    forecast: detail.forecast
      ? {
          prob: detail.forecast.model_prob,
          confidence: local?.forecast.confidence ?? 0.5,
          edge: local?.forecast.edge ?? 0,
          brier: local?.forecast.brier ?? 0,
          reasoning:
            local?.forecast.reasoning ??
            "API-backed market forecast generated from current market proof.",
          // Pass ensemble/tool fields through only when the backend supplied them.
          ...(detail.forecast.n_models !== undefined ? { nModels: detail.forecast.n_models } : {}),
          ...(detail.forecast.stdev !== undefined ? { stdev: detail.forecast.stdev } : {}),
          ...(detail.forecast.spread_flag !== undefined
            ? { spreadFlag: detail.forecast.spread_flag }
            : {}),
          ...(detail.forecast.per_model !== undefined
            ? { perModel: detail.forecast.per_model }
            : {}),
          ...(detail.forecast.tools_used !== undefined
            ? { toolsUsed: detail.forecast.tools_used }
            : {}),
        }
      : local?.forecast ?? {
          prob: 0.5,
          confidence: 0.5,
          edge: 0,
          brier: 0,
          reasoning: "Forecast unavailable.",
        },
    bids: local?.bids ?? [],
    asks: local?.asks ?? [],
    trades: local?.trades ?? [],
    holders: local?.holders ?? [],
    comments: local?.comments ?? [],
    seed: local?.seed ?? 0,
    description: local?.description ?? detail.resolution_criteria,
    resolution: detail.resolution_criteria,
  };
}

// ── U06 Clone API ────────────────────────────────────────────────────────────

export type CloneConfig = {
  id: string;
  clone_id: string;
  version: number;
  name: string;
  nodes: string[];
  markets: string[];
  edge_threshold: number;
  cooldown_minutes: number;
  is_latest: boolean;
  paper_trading_only: boolean;
  created_at: string;
};

export type CloneRun = {
  id: string;
  clone_id: string;
  clone_version_id: string;
  market_slug: string;
  status: "pending" | "running" | "done" | "error";
  trace: Array<{ step_name: string; input_data: Record<string, unknown>; output_data: Record<string, unknown> }>;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

export async function fetchVettedNodes(token?: string): Promise<string[]> {
  if (!API_BASE) return [];
  try {
    const res = await fetch(`${API_BASE}/api/v1/clones/nodes`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { nodes?: string[] };
    return data.nodes ?? [];
  } catch {
    return [];
  }
}

export async function fetchClones(token: string): Promise<CloneConfig[]> {
  if (!API_BASE || !token) return [];
  try {
    const res = await fetch(`${API_BASE}/api/v1/clones`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { clones?: CloneConfig[] };
    return data.clones ?? [];
  } catch {
    return [];
  }
}

export async function createClone(
  token: string,
  payload: { name: string; nodes: string[]; markets: string[]; edge_threshold: number; cooldown_minutes: number },
): Promise<CloneConfig | null> {
  if (!API_BASE || !token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/clones`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return null;
    return (await res.json()) as CloneConfig;
  } catch {
    return null;
  }
}

export async function runClone(
  token: string,
  cloneId: string,
  marketSlug: string,
): Promise<CloneRun | null> {
  if (!API_BASE || !token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/clones/${cloneId}/run`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ market_slug: marketSlug }),
    });
    if (!res.ok) return null;
    return (await res.json()) as CloneRun;
  } catch {
    return null;
  }
}

export async function fetchCloneRuns(
  token: string,
  cloneId: string,
  limit = 20,
): Promise<CloneRun[]> {
  if (!API_BASE || !token) return [];
  try {
    const res = await fetch(`${API_BASE}/api/v1/clones/${cloneId}/runs?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { runs?: CloneRun[] };
    return data.runs ?? [];
  } catch {
    return [];
  }
}

function fallbackForSlug(slug: string): MarketSnapshot {
  if (slug === CANONICAL_SLUG) {
    return fallbackSnapshot;
  }
  return {
    ...fallbackSnapshot,
    market: {
      ...fallbackSnapshot.market,
      slug,
      title: slug,
      question: "Paper market snapshot unavailable",
    },
  };
}
