import { mergeApiMarketsForCards, type ApiMarketCatalogItem } from "./api-market-adapter";
import { mergeApiSnapshotForDetail } from "./api-market-detail-adapter";
import { MARKETS, type Market as CardMarket } from "./mock-data";
import type { Market, MarketSnapshot } from "./market-view-model";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
export const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "";
export const PAPER_BALANCE = 100_000;
export const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

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
  sort?: "volume" | "traders" | "newest";
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

export async function fetchMarkets(params?: MarketFilterParams): Promise<CardMarket[]> {
  if (!API_BASE) {
    return MARKETS;
  }

  try {
    const url = new URL(`${API_BASE}/api/v1/markets`);
    if (params?.category && params.category !== "all") {
      url.searchParams.set("category", params.category);
    }
    if (params?.sort) url.searchParams.set("sort", params.sort);
    if (params?.q) url.searchParams.set("q", params.q);

    const response = await fetch(url.toString(), { cache: "no-store" });
    if (!response.ok) {
      return MARKETS;
    }
    const markets = (await response.json()) as ApiMarketCatalogItem[];
    return markets.length ? mergeApiMarketsForCards(markets, MARKETS) : MARKETS;
  } catch {
    return MARKETS;
  }
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
  if (!API_BASE) {
    return fallbackForSlug(slug);
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/markets/${slug}/snapshot`, {
      cache: "no-store",
    });
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
  } | null;
  volume_usd: number;
  traders: number;
  resolution_criteria: string;
  paper_trading_only: boolean;
  resolved: boolean;
  resolution_outcome: "YES" | "NO" | null;
};

export async function fetchMarketDetailApi(
  slug: string,
): Promise<MarketDetailApi | null> {
  if (!API_BASE) {
    return null;
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/markets/${slug}/detail`, {
      cache: "no-store",
    });
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

  if (!API_BASE) {
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
