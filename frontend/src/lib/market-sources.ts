import type { Market } from "./mock-data";

export function isKalshiSource(market: Market): boolean {
  const src = (market.source ?? "").toLowerCase();
  return src === "kalshi" || market.slug.startsWith("ks-");
}

export function isPolymarketSource(market: Market): boolean {
  const src = (market.source ?? "").toLowerCase();
  return src === "polymarket" || market.slug.startsWith("pm-");
}

export function filterKalshiMarkets(markets: Market[]): Market[] {
  return markets.filter(isKalshiSource);
}

export function filterPolymarketMarkets(markets: Market[]): Market[] {
  return markets.filter(isPolymarketSource);
}
