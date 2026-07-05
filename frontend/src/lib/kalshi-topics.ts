import type { Market } from "./mock-data";
import { toApiCategory } from "./alphaedge-api";

export type KalshiTopicId =
  | "trending"
  | "sports"
  | "politics"
  | "crypto"
  | "culture"
  | "economics"
  | "tech";

export type KalshiTopic = {
  id: KalshiTopicId;
  label: string;
};

export const KALSHI_TOPICS: KalshiTopic[] = [
  { id: "trending", label: "Trending" },
  { id: "sports", label: "Sports" },
  { id: "politics", label: "Politics" },
  { id: "crypto", label: "Crypto" },
  { id: "culture", label: "Culture" },
  { id: "economics", label: "Economics" },
  { id: "tech", label: "Tech" },
];

function categoryMatches(market: Market, topic: KalshiTopicId): boolean {
  if (topic === "trending") return true;
  const cat = market.category.toLowerCase();
  const slug = market.slug.toLowerCase();
  switch (topic) {
    case "sports":
      return (
        cat === "sports" ||
        cat === "nba" ||
        cat === "fifa wc2026" ||
        slug.startsWith("nba-") ||
        slug.startsWith("wc2026-") ||
        slug.startsWith("ks-kxwcgame") ||
        slug.includes("fifwc") ||
        slug.includes("fifa")
      );
    case "politics":
      return (
        cat === "politics" ||
        cat === "elections" ||
        slug.startsWith("elect-")
      );
    case "crypto":
      return cat === "crypto" || slug.startsWith("crypto-");
    case "culture":
      return cat === "culture" || slug.startsWith("culture-");
    case "economics":
      return cat === "economics";
    case "tech":
      return cat === "tech" || /\b(tech|ai|science)\b/i.test(market.title);
    default:
      return true;
  }
}

export function filterByTopic(markets: Market[], topic: KalshiTopicId): Market[] {
  return markets.filter((m) => categoryMatches(m, topic));
}

export function topicToApiCategory(topic: KalshiTopicId): string | undefined {
  if (topic === "trending") return undefined;
  const map: Record<KalshiTopicId, string | undefined> = {
    trending: undefined,
    sports: "sports",
    politics: "politics",
    crypto: "crypto",
    culture: "culture",
    economics: "economics",
    tech: undefined,
  };
  const raw = map[topic];
  return raw ? toApiCategory(raw) : undefined;
}
