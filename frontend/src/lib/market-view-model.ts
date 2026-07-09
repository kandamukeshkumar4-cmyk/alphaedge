export type MarketStatus = "open" | "locked" | "resolved";
export type Outcome = "yes" | "no";

export type Market = {
  id: string;
  slug: string;
  title: string;
  question: string;
  category: string;
  icon: string;
  volume: number;
  traders: number;
  market_count: number;
  description: string;
  resolution: string;
  status: MarketStatus;
  lock_at: string | null;
  resolved_at: string | null;
  winning_outcome: Outcome | null;
};

export type BookLevel = {
  price: number;
  size: number;
};

export type OutcomeBook = {
  bids: BookLevel[];
  asks: BookLevel[];
};

export type MarketActivity = {
  id: string;
  outcome: Outcome;
  price: number;
  quantity: number;
  created_at: string;
};

export type MarketSnapshot = {
  paper_trading_only: boolean;
  disclaimer: string;
  market: Market;
  book: {
    yes: OutcomeBook;
    no: OutcomeBook;
  };
  activity: MarketActivity[];
  forecast: {
    predicted_prob: number;
    confidence: number;
    edge_vs_book: number | null;
    input_feature_hash: string | null;
  } | null;
  evaluation: {
    latest_brier_score: number;
    predicted_prob: number | null;
    actual_outcome: number;
    closing_implied: number | null;
  } | null;
};

export function formatProbability(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}

export function formatMultiplier(price: number | null | undefined): string {
  if (!price || Number.isNaN(price) || price <= 0) {
    return "-";
  }
  return `${(1 / price).toFixed(2)}x`;
}

export function buildMarketDetailView(snapshot: MarketSnapshot) {
  const yesPrice = bestDisplayPrice(snapshot.book.yes, snapshot.forecast?.predicted_prob ?? 0.5);
  const noPrice = bestDisplayPrice(snapshot.book.no, 1 - yesPrice);

  return {
    slug: snapshot.market.slug,
    title: snapshot.market.title,
    question: snapshot.market.question,
    statusLabel: titleCase(snapshot.market.status),
    primaryPriceLabel: formatProbability(yesPrice),
    paperOnlyLabel: snapshot.paper_trading_only ? "Paper trading only" : "Unavailable",
    outcomes: [
      outcomeView("YES", yesPrice, snapshot.book.yes),
      outcomeView("NO", noPrice, snapshot.book.no),
    ],
    forecast: snapshot.forecast
      ? {
          probabilityLabel: formatProbability(snapshot.forecast.predicted_prob),
          confidenceLabel: formatProbability(snapshot.forecast.confidence),
          edgeLabel: formatSignedProbability(snapshot.forecast.edge_vs_book),
          verdict: forecastVerdict(snapshot.forecast.edge_vs_book),
          inputFeatureHash: snapshot.forecast.input_feature_hash,
        }
      : null,
    evaluation: snapshot.evaluation
      ? {
          brierLabel: snapshot.evaluation.latest_brier_score.toFixed(4),
          predictedLabel: formatProbability(snapshot.evaluation.predicted_prob),
          closingLabel: formatProbability(snapshot.evaluation.closing_implied),
        }
      : null,
    activity: snapshot.activity.map((item) => ({
      ...item,
      outcomeLabel: item.outcome.toUpperCase(),
      priceLabel: formatProbability(item.price),
      summary: `${item.outcome.toUpperCase()} filled at ${formatProbability(item.price)} for ${
        item.quantity
      } shares`,
    })),
  };
}

export function buildTradeTicketPreview({
  price,
  shares,
  balance,
}: {
  price: number;
  shares: number;
  balance: number;
}) {
  const cost = price * shares;
  const toWin = shares;
  const potentialProfit = toWin - cost;
  const balanceAfter = balance - cost;

  return {
    cost,
    toWin,
    potentialProfit,
    balanceAfter,
    costLabel: formatCurrency(cost),
    toWinLabel: formatCurrency(toWin),
    potentialProfitLabel: `${potentialProfit >= 0 ? "+" : "-"}${formatCurrency(
      Math.abs(potentialProfit),
    )}`,
    balanceAfterLabel: formatCurrency(balanceAfter),
  };
}

function outcomeView(label: "YES" | "NO", price: number, book: OutcomeBook) {
  return {
    label,
    bestPrice: price,
    bestPriceLabel: formatProbability(price),
    multiplierLabel: formatMultiplier(price),
    bidSize: book.bids[0]?.size ?? 0,
    askSize: book.asks[0]?.size ?? 0,
  };
}

function bestDisplayPrice(book: OutcomeBook, fallback: number): number {
  return book.asks[0]?.price ?? book.bids[0]?.price ?? fallback;
}

function forecastVerdict(edge: number | null): string {
  if (edge === null) {
    return "No book reference";
  }
  if (edge > 0.005) {
    return "Positive model edge";
  }
  if (edge < -0.005) {
    return "Negative model edge";
  }
  return "In line with book";
}

function formatSignedProbability(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  const percent = Math.round(Math.abs(value) * 100);
  return `${value >= 0 ? "+" : "-"}${percent}%`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function titleCase(value: string): string {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1).toLowerCase()}`;
}
