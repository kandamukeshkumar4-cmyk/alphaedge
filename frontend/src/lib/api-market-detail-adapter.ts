import type { MarketSnapshot } from "./market-view-model";
import {
  type Category,
  type Market,
  type MarketOutcome,
  type OutcomeTone,
  type Trade,
} from "./mock-data";
import { mergeApiMarketsForCards } from "./api-market-adapter";

export function mergeApiSnapshotForDetail(
  snapshot: MarketSnapshot,
  localMarkets: Market[],
): Market {
  const [catalogMarket] = mergeApiMarketsForCards([snapshot.market], localMarkets);
  const yesPrice = bestPrice(snapshot.book.yes.asks, snapshot.book.yes.bids, snapshot.forecast?.predicted_prob ?? catalogMarket.outcomes[0]?.price ?? 0.5);
  const noPrice = bestPrice(snapshot.book.no.asks, snapshot.book.no.bids, 1 - yesPrice);
  const forecast = snapshot.forecast
    ? {
        prob: snapshot.forecast.predicted_prob,
        confidence: snapshot.forecast.confidence,
        edge: snapshot.forecast.edge_vs_book ?? 0,
        brier: snapshot.evaluation?.latest_brier_score ?? catalogMarket.forecast.brier,
        reasoning:
          catalogMarket.forecast.reasoning ||
          "API-backed market forecast generated from current market proof.",
      }
    : catalogMarket.forecast;

  return {
    ...catalogMarket,
    outcomes: mergeBinaryOutcomes(catalogMarket.outcomes, yesPrice, noPrice),
    bids: snapshot.book.yes.bids.length ? snapshot.book.yes.bids : catalogMarket.bids,
    asks: snapshot.book.yes.asks.length ? snapshot.book.yes.asks : catalogMarket.asks,
    forecast,
    trades: snapshot.activity.length
      ? mapSnapshotActivity(snapshot.activity, catalogMarket.outcomes, Date.now())
      : catalogMarket.trades,
  };
}

function mergeBinaryOutcomes(
  existing: MarketOutcome[],
  yesPrice: number,
  noPrice: number,
): MarketOutcome[] {
  const yes = existing[0] ?? fallbackOutcome("yes", "YES", "Y", "primary");
  const no = existing[1] ?? fallbackOutcome("no", "NO", "N", "danger");
  return [
    { ...yes, price: yesPrice },
    { ...no, price: noPrice },
    ...existing.slice(2),
  ];
}

function fallbackOutcome(
  id: string,
  label: string,
  emoji: string,
  tone: OutcomeTone,
): MarketOutcome {
  return {
    id,
    label,
    emoji,
    price: 0.5,
    prevPrice: 0.5,
    tone,
  };
}

function bestPrice(
  asks: Array<{ price: number; size: number }>,
  bids: Array<{ price: number; size: number }>,
  fallback: number,
): number {
  return asks[0]?.price ?? bids[0]?.price ?? fallback;
}

function mapSnapshotActivity(
  activity: MarketSnapshot["activity"],
  outcomes: MarketOutcome[],
  nowMs: number,
): Trade[] {
  return activity.map((item) => {
    const side = item.outcome.toUpperCase() as "YES" | "NO";
    const outcomeIndex = item.outcome === "yes" ? 0 : 1;
    const createdAtMs = new Date(item.created_at).getTime();
    const tsOffsetSec = Number.isNaN(createdAtMs)
      ? 0
      : Math.max(0, Math.round((nowMs - createdAtMs) / 1000));

    return {
      id: item.id,
      user: "market_feed",
      side,
      outcome: outcomes[outcomeIndex]?.label ?? side,
      price: item.price,
      shares: item.quantity,
      tsOffsetSec,
    };
  });
}

export type { Category };
