import { API_BASE } from "./alphaedge-api";

export type Market = {
  id: string;
  slug: string;
  title: string;
  platform: string;
  status: string;
  implied_yes: number | null;
  category: string;
};

type ApiMarketCatalogItem = {
  id: string;
  slug: string;
  title: string;
  category: string;
  status: string;
  platform?: string;
  implied_yes?: number | null;
};

function normalizePlatform(value: string | undefined): string {
  if (!value) {
    return "Polymarket";
  }
  const lower = value.toLowerCase();
  if (lower === "kalshi") {
    return "Kalshi";
  }
  if (lower === "polymarket") {
    return "Polymarket";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function toMarket(item: ApiMarketCatalogItem): Market {
  return {
    id: item.id,
    slug: item.slug,
    title: item.title,
    platform: normalizePlatform(item.platform),
    status: item.status,
    implied_yes: item.implied_yes ?? null,
    category: item.category,
  };
}

function matchesFilter(market: Market, filter?: "open" | "resolved"): boolean {
  if (!filter) {
    return true;
  }
  if (filter === "open") {
    return market.status === "open" || market.status === "locked";
  }
  return market.status === "resolved";
}

export async function fetchMarkets(filter?: "open" | "resolved"): Promise<Market[]> {
  if (!API_BASE) {
    return [];
  }

  const response = await fetch(`${API_BASE}/api/v1/markets`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Markets HTTP ${response.status}`);
  }

  const items = (await response.json()) as ApiMarketCatalogItem[];
  return items.map(toMarket).filter((market) => matchesFilter(market, filter));
}
