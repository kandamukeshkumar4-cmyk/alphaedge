import { describe, expect, it } from "vitest";

import { MARKETS } from "./mock-data";
import { buildCultSignalModel } from "./cult-signal-model";

describe("cult signal model", () => {
  it("builds a paper-trading decision stack from a market", () => {
    const model = buildCultSignalModel(MARKETS[0]);

    expect(model.marketTitle).toBe("Lakers vs Celtics");
    expect(model.paperTradingOnly).toBe(true);
    expect(model.executionGuardrail).toBe(
      "RiskService -> validated OrderIntent -> OrderBookService",
    );
    expect(model.poll.options.map((option) => option.label)).toEqual([
      "Lakers",
      "Celtics",
    ]);
    expect(model.poll.defaultSelection).toBe(MARKETS[0].outcomes[0].id);
    expect(model.poll.totalVotes).toBe(MARKETS[0].traders);
    expect(model.riskChecks.map((check) => check.label)).toEqual([
      "Paper bankroll",
      "Risk gate",
      "Resolution rule",
      "Calibration watch",
    ]);
    expect(model.toolStack.map((tool) => tool.id)).toEqual([
      "book",
      "model",
      "community",
      "risk",
    ]);
  });

  it("surfaces negative edge as a wait verdict", () => {
    const market = {
      ...MARKETS[0],
      forecast: {
        ...MARKETS[0].forecast,
        edge: -0.04,
      },
    };

    const model = buildCultSignalModel(market);

    expect(model.edgeTone).toBe("danger");
    expect(model.edgeVerdict).toBe("Book may be rich");
  });

  it("uses backend signal tallies when available", () => {
    const model = buildCultSignalModel(MARKETS[0], {
      selected_outcome: "no",
      total_signals: 4,
      options: [
        { outcome: "yes", count: 1, percentage: 25 },
        { outcome: "no", count: 3, percentage: 75 },
      ],
    });

    expect(model.poll.totalVotes).toBe(4);
    expect(model.poll.defaultSelection).toBe(MARKETS[0].outcomes[1].id);
    expect(model.poll.options.map((option) => option.apiOutcome)).toEqual([
      "yes",
      "no",
    ]);
    expect(model.poll.votes).toEqual({
      [MARKETS[0].outcomes[0].id]: 1,
      [MARKETS[0].outcomes[1].id]: 3,
    });
  });
});
