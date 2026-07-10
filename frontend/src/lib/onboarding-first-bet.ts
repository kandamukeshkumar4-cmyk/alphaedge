import type { Market } from "./mock-data";

/**
 * F05: pick a liquid, still-open market to suggest for a first paper trade.
 * Highest volume among open markets. Pure + deterministic so the flow is
 * testable. Returns null when there is nothing tradeable to suggest.
 */
export function pickSuggestedMarket(markets: Market[]): Market | null {
  const tradeable = markets.filter(
    (m) => m.status === undefined || m.status === "open",
  );
  if (tradeable.length === 0) return null;
  return tradeable.reduce((best, m) => (m.volume > best.volume ? m : best));
}

export type FirstBetStep = {
  key: "price" | "edge" | "trade";
  title: string;
  body: string;
};

/** The three guided steps: what a price means → what our edge means → trade. */
export const FIRST_BET_STEPS: FirstBetStep[] = [
  {
    key: "price",
    title: "What a price means",
    body: "A market price is a probability. YES at 62¢ means the crowd thinks there's a 62% chance it happens. Prices move as new money and news arrive — they are not a guarantee.",
  },
  {
    key: "edge",
    title: "What our edge & signals mean",
    body: "Our model estimates its own probability. When it disagrees with the market, that gap is the edge — but we only call it edge once the closing-line track record backs it up. Signals (news, whale flow, arb) are research context, never auto-trades.",
  },
  {
    key: "trade",
    title: "Place your first paper trade",
    body: "Everything here is simulated funds — no real money, ever. Try a liquid market below to see how a paper order works.",
  },
];
