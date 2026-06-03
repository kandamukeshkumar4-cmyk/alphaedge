import {
  formatCompactUSD,
  pct,
  timeUntil,
  type Market,
  type MarketOutcome,
} from "./mock-data";

export type CultSignalTone = "primary" | "danger" | "accent" | "muted" | "gold";
export type SignalCheckStatus = "pass" | "watch";

export type CultSignalPollOption = {
  id: string;
  label: string;
  emoji: string;
  priceLabel: string;
  apiOutcome: "yes" | "no" | null;
};

export type CultSignalTool = {
  id: "book" | "model" | "community" | "risk";
  label: string;
  value: string;
  detail: string;
  tone: CultSignalTone;
};

export type CultSignalRiskCheck = {
  label: string;
  detail: string;
  status: SignalCheckStatus;
};

export type CultSignalModel = {
  marketTitle: string;
  closeLabel: string;
  edgeTone: CultSignalTone;
  edgeVerdict: string;
  paperTradingOnly: true;
  executionGuardrail: string;
  poll: {
    question: string;
    options: CultSignalPollOption[];
    votes: Record<string, number>;
    totalVotes: number;
    defaultSelection: string;
  };
  toolStack: CultSignalTool[];
  riskChecks: CultSignalRiskCheck[];
};

export type PaperSignalSnapshot = {
  selected_outcome: "yes" | "no" | null;
  total_signals: number;
  options: Array<{
    outcome: "yes" | "no";
    count: number;
    percentage: number;
  }>;
};

const EXECUTION_GUARDRAIL = "RiskService -> validated OrderIntent -> OrderBookService";

export function buildCultSignalModel(
  market: Market,
  signalSnapshot?: PaperSignalSnapshot | null,
): CultSignalModel {
  const topOutcome = getTopOutcome(market.outcomes);
  const edgeTone = getEdgeTone(market.forecast.edge);
  const outcomeMap = buildOutcomeMap(market.outcomes);
  const votes = signalSnapshot
    ? votesFromSignalSnapshot(market.outcomes, signalSnapshot)
    : allocateVotes(market.outcomes, market.traders);
  const selectedOutcome = signalSnapshot?.selected_outcome
    ? outcomeMap[signalSnapshot.selected_outcome]
    : undefined;

  return {
    marketTitle: market.title,
    closeLabel: timeUntil(market.endsAt),
    edgeTone,
    edgeVerdict: getEdgeVerdict(edgeTone),
    paperTradingOnly: true,
    executionGuardrail: EXECUTION_GUARDRAIL,
    poll: {
      question: `Trader signal for ${market.title}`,
      options: market.outcomes.map((outcome, index) => ({
        id: outcome.id,
        label: outcome.label,
        emoji: outcome.emoji,
        priceLabel: pct(outcome.price),
        apiOutcome: index === 0 ? "yes" : index === 1 ? "no" : null,
      })),
      votes,
      totalVotes: signalSnapshot?.total_signals ?? market.traders,
      defaultSelection: selectedOutcome?.id ?? topOutcome.id,
    },
    toolStack: [
      {
        id: "book",
        label: "Book price",
        value: pct(topOutcome.price),
        detail: `${topOutcome.label} leads on ${formatCompactUSD(market.volume)} volume`,
        tone: topOutcome.tone,
      },
      {
        id: "model",
        label: "Model edge",
        value: formatSignedPct(market.forecast.edge),
        detail: `${pct(market.forecast.confidence)} confidence`,
        tone: edgeTone,
      },
      {
        id: "community",
        label: "Trader poll",
        value: market.traders.toLocaleString(),
        detail: "Seeded from active paper traders",
        tone: "gold",
      },
      {
        id: "risk",
        label: "Risk gate",
        value: "Paper only",
        detail: "Orders stay inside the simulated account path",
        tone: "muted",
      },
    ],
    riskChecks: [
      {
        label: "Paper bankroll",
        detail: "$100,000 simulated funds; no deposits or withdrawals.",
        status: "pass",
      },
      {
        label: "Risk gate",
        detail: EXECUTION_GUARDRAIL,
        status: "pass",
      },
      {
        label: "Resolution rule",
        detail: market.resolution,
        status: "pass",
      },
      {
        label: "Calibration watch",
        detail: `Latest Brier ${market.forecast.brier.toFixed(3)}`,
        status: market.forecast.brier <= 0.15 ? "pass" : "watch",
      },
    ],
  };
}

function buildOutcomeMap(outcomes: MarketOutcome[]): Partial<Record<"yes" | "no", MarketOutcome>> {
  return {
    yes: outcomes[0],
    no: outcomes[1],
  };
}

function votesFromSignalSnapshot(
  outcomes: MarketOutcome[],
  signalSnapshot: PaperSignalSnapshot,
): Record<string, number> {
  const votes: Record<string, number> = {};
  const counts = Object.fromEntries(
    signalSnapshot.options.map((option) => [option.outcome, option.count]),
  ) as Partial<Record<"yes" | "no", number>>;

  outcomes.forEach((outcome, index) => {
    if (index === 0) {
      votes[outcome.id] = counts.yes ?? 0;
    } else if (index === 1) {
      votes[outcome.id] = counts.no ?? 0;
    } else {
      votes[outcome.id] = 0;
    }
  });
  return votes;
}

function getTopOutcome(outcomes: MarketOutcome[]): MarketOutcome {
  return outcomes.reduce((best, outcome) =>
    outcome.price > best.price ? outcome : best,
  );
}

function allocateVotes(
  outcomes: MarketOutcome[],
  totalVotes: number,
): Record<string, number> {
  if (outcomes.length === 0 || totalVotes <= 0) {
    return {};
  }

  const weights = outcomes.map((outcome) => Math.max(outcome.price, 0.01));
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  let allocated = 0;

  return outcomes.reduce<Record<string, number>>((votes, outcome, index) => {
    const isLast = index === outcomes.length - 1;
    const count = isLast
      ? totalVotes - allocated
      : Math.round((weights[index] / totalWeight) * totalVotes);

    allocated += count;
    votes[outcome.id] = Math.max(0, count);
    return votes;
  }, {});
}

function getEdgeTone(edge: number): CultSignalTone {
  if (edge >= 0.015) {
    return "primary";
  }
  if (edge <= -0.015) {
    return "danger";
  }
  return "muted";
}

function getEdgeVerdict(tone: CultSignalTone): string {
  if (tone === "primary") {
    return "Positive model edge";
  }
  if (tone === "danger") {
    return "Book may be rich";
  }
  return "Fairly priced";
}

function formatSignedPct(value: number): string {
  const rounded = Math.round(value * 100);
  return `${rounded >= 0 ? "+" : ""}${rounded}%`;
}
