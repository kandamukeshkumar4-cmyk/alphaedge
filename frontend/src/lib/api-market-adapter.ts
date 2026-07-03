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
  source?: string;
  image_url?: string | null;
  yes_price?: number | null;
};

/** Map API catalog rows to card markets — API is the sole source of truth. */
export function apiCatalogToMarkets(apiMarkets: ApiMarketCatalogItem[]): Market[] {
  return apiMarkets.map((apiMarket) =>
    buildApiOnlyMarket(apiMarket, coerceCategory(apiMarket.category)),
  );
}

/** @deprecated Prefer apiCatalogToMarkets; kept for tests that merge legacy mock shapes. */
export function mergeApiMarketsForCards(
  apiMarkets: ApiMarketCatalogItem[],
  localMarkets: Market[],
): Market[] {
  return apiMarkets.map((apiMarket) => {
    const local = localMarkets.find((market) => market.slug === apiMarket.slug);
    const category = coerceCategory(apiMarket.category);
    if (local) {
      const merged = {
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
        source: apiMarket.source ?? local.source,
        imageUrl: apiMarket.image_url ?? local.imageUrl,
      };
      if (typeof apiMarket.yes_price === "number") {
        merged.outcomes = buildBinaryOutcomes(apiMarket.yes_price);
      }
      return merged;
    }

    return buildApiOnlyMarket(apiMarket, category);
  });
}

function buildApiOnlyMarket(apiMarket: ApiMarketCatalogItem, category: Category): Market {
  const seed = hashSeed(apiMarket.slug);
  const hasPrice = typeof apiMarket.yes_price === "number";
  const price = hasPrice ? apiMarket.yes_price! : 0;
  const outcomes = hasPrice
    ? buildBinaryOutcomes(price)
    : buildBinaryOutcomes(0.5).map((o) => ({ ...o, price: 0, prevPrice: 0 }));
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
    trendDelta: 0,
    outcomes,
    forecast: {
      prob: hasPrice ? price : 0,
      confidence: 0,
      edge: 0,
      brier: 0,
      reasoning: "",
    },
    bids: [],
    asks: [],
    description: apiMarket.description,
    resolution: apiMarket.resolution,
    trades: [],
    holders: [],
    comments: [],
    seed,
    source: apiMarket.source,
    imageUrl: apiMarket.image_url ?? undefined,
    status: apiMarket.status,
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
  const normalized = value.trim();
  if ((CATEGORIES as string[]).includes(normalized)) {
    return normalized as Category;
  }
  const lower = normalized.toLowerCase();
  if (lower === "elections" || lower === "politics") return "Politics";
  if (lower === "nba" || lower === "fifa wc2026" || lower === "sports") return "Sports";
  if (lower === "crypto") return "Crypto";
  if (lower === "culture") return "Culture";
  if (lower === "economics") return "Economics";
  return "Sports";
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

function hashSeed(value: string): number {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
