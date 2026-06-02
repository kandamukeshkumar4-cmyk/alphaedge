import { mergeApiMarketsForCards, type ApiMarketCatalogItem } from "./api-market-adapter";
import { mergeApiSnapshotForDetail } from "./api-market-detail-adapter";
import { MARKETS, type Market as CardMarket } from "./mock-data";
import type { Market, MarketSnapshot } from "./market-view-model";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
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

export async function fetchMarkets(): Promise<CardMarket[]> {
  if (!API_BASE) {
    return MARKETS;
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/markets`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return MARKETS;
    }
    const markets = (await response.json()) as ApiMarketCatalogItem[];
    return markets.length ? mergeApiMarketsForCards(markets, MARKETS) : MARKETS;
  } catch {
    return MARKETS;
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

export async function fetchMarketDetail(slug: string): Promise<CardMarket | null> {
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
