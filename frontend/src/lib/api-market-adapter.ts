import {
  CATEGORIES,
  type Category,
  type Market,
  type MarketOutcome,
  type OutcomeTone,
} from "./mock-data";

export type ApiMarketCatalogItem = {
  id: string;
  slug: string;
  title: string;
  question: string;
  status: "open" | "locked" | "resolved";
  lock_at: string | null;
  resolved_at: string | null;
  winning_outcome: "yes" | "no" | null;
  category: string;
  icon: string;
  volume: number;
  traders: number;
  market_count: number;
  description: string;
  resolution: string;
};

export function mergeApiMarketsForCards(
  apiMarkets: ApiMarketCatalogItem[],
  localMarkets: Market[],
): Market[] {
  return apiMarkets.map((apiMarket) => {
    const local = localMarkets.find((market) => market.slug === apiMarket.slug);
    const category = coerceCategory(apiMarket.category);
    if (local) {
      return {
        ...local,
        id: apiMarket.id,
        title: apiMarket.title,
        question: apiMarket.question,
        category,
        icon: apiMarket.icon || local.icon,
        endsAt: apiMarket.lock_at ?? local.endsAt,
        volume: apiMarket.volume,
        traders: apiMarket.traders,
        marketCount: apiMarket.market_count,
        description: apiMarket.description || local.description,
        resolution: apiMarket.resolution || local.resolution,
      };
    }

    return buildApiOnlyMarket(apiMarket, category);
  });
}

function buildApiOnlyMarket(apiMarket: ApiMarketCatalogItem, category: Category): Market {
  const seed = hashSeed(apiMarket.slug);
  const price = priceFromSeed(seed);
  const outcomes = buildBinaryOutcomes(price);
  return {
    id: apiMarket.id,
    slug: apiMarket.slug,
    category,
    icon: apiMarket.icon || iconForCategory(category),
    title: apiMarket.title,
    question: apiMarket.question,
    endsAt: apiMarket.lock_at ?? new Date(Date.now() + 7 * 86_400_000).toISOString(),
    volume: apiMarket.volume,
    traders: apiMarket.traders,
    marketCount: apiMarket.market_count,
    trendDelta: Math.round(((seed % 41) - 20) * 1.5),
    outcomes,
    forecast: {
      prob: Math.min(0.97, price + 0.04),
      confidence: 0.74,
      edge: 0.06,
      brier: 0.18,
      reasoning: "API-backed paper market awaiting richer model lineage.",
    },
    bids: [
      { price: Math.max(0.01, price - 0.02), size: 820 },
      { price: Math.max(0.01, price - 0.03), size: 540 },
    ],
    asks: [
      { price: Math.min(0.99, price + 0.02), size: 760 },
      { price: Math.min(0.99, price + 0.03), size: 510 },
    ],
    description: apiMarket.description,
    resolution: apiMarket.resolution,
    trades: [],
    holders: [],
    comments: [],
    seed,
  };
}

function buildBinaryOutcomes(price: number): MarketOutcome[] {
  return [
    {
      id: "yes",
      label: "YES",
      emoji: "Y",
      price,
      prevPrice: Math.max(0.03, price - 0.02),
      tone: "primary",
    },
    {
      id: "no",
      label: "NO",
      emoji: "N",
      price: 1 - price,
      prevPrice: Math.min(0.97, 1 - price + 0.02),
      tone: "danger",
    },
  ];
}

function coerceCategory(value: string): Category {
  return (CATEGORIES as string[]).includes(value) ? (value as Category) : "Sports";
}

function iconForCategory(category: Category): string {
  const icons: Record<Category, string> = {
    Sports: "S",
    Politics: "P",
    Crypto: "C",
    Culture: "A",
    Economics: "E",
  };
  return icons[category];
}

function priceFromSeed(seed: number): number {
  return 0.35 + (seed % 31) / 100;
}

function hashSeed(value: string): number {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
