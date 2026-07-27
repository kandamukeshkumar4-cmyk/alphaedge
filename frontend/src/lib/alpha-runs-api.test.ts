import { afterEach, describe, expect, it } from "vitest";

import {
  alphaRunStatusLabel,
  getHypotheses,
  getLatestSignal,
  getRuns,
  resetAlphaRunsFetch,
  setAlphaRunsFetch,
} from "@/lib/alpha-runs-api";

function jsonFetch(payload: unknown, status = 200): typeof fetch {
  return (async () =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
}

const failingFetch = (async () =>
  new Response("nope", { status: 500 })) as typeof fetch;

/**
 * Prod-shape fixtures — copied from
 * `GET https://alphaedge-api-production-b9db.up.railway.app/api/v1/alpha/*`
 * on 2026-07-27 (trimmed to the fields the normalizer reads).
 */
const PROD_RUNS_PAYLOAD = {
  latest: {
    id: "bdb65fcb-d4cd-4ff5-b603-ea5f24053709",
    run_date: "2026-07-27",
    status: "no_signal",
    result: {
      decomposition: {
        status: "no_signal",
        reason: "portfolio_not_constructed",
        residual_alpha: null,
        residual_alpha_t_stat: null,
        threshold: 2.5,
      },
      signal: {
        label: "no signal (evidence)",
        status: "no_signal",
        weights: {},
        residual_alpha_t_stat: null,
        threshold: 2.5,
      },
    },
    rejection_reasons: [
      {
        node: "validator",
        factor: "model_edge",
        reason: "oos_does_not_beat_closing",
      },
    ],
    paper_trading_only: true,
    reused: false,
  },
  runs: [
    {
      id: "bdb65fcb-d4cd-4ff5-b603-ea5f24053709",
      run_date: "2026-07-27",
      status: "no_signal",
      result: {
        decomposition: {
          status: "no_signal",
          reason: "portfolio_not_constructed",
          residual_alpha: null,
          residual_alpha_t_stat: null,
          threshold: 2.5,
        },
        signal: {
          label: "no signal (evidence)",
          status: "no_signal",
          weights: {},
          residual_alpha_t_stat: null,
          threshold: 2.5,
        },
      },
      rejection_reasons: [
        {
          node: "validator",
          factor: "model_edge",
          reason: "oos_does_not_beat_closing",
        },
      ],
      paper_trading_only: true,
      reused: false,
    },
    {
      // Tolerant path: residual_alpha as string nested under decomposition,
      // missing id — still usable.
      run_date: "2026-07-26",
      status: "genuine_edge",
      result: {
        decomposition: {
          status: "genuine_edge",
          residual_alpha: "0.018",
          residual_alpha_t_stat: 2.74,
        },
        signal: { status: "genuine_edge", residual_alpha_t_stat: 2.74 },
      },
      paper_trading_only: true,
    },
  ],
  paper_trading_only: true,
};

const PROD_LATEST_SIGNAL_PAYLOAD = {
  run_date: "2026-07-27",
  signal: {
    label: "no signal (evidence)",
    status: "no_signal",
    weights: {},
    residual_alpha_t_stat: null,
    threshold: 2.5,
  },
  rejection_reasons: [
    {
      node: "validator",
      factor: "model_edge",
      reason: "oos_does_not_beat_closing",
    },
    {
      node: "portfolio_constructor",
      reason: "insufficient_common_oos_returns",
    },
  ],
  paper_trading_only: true,
};

const PROD_EMITTED_SIGNAL_PAYLOAD = {
  run_date: "2026-07-23",
  signal: {
    label: "genuine edge",
    status: "genuine_edge",
    weights: { model_edge: 0.4, time_decay: 0.6, bad_entry: "junk" },
    residual_alpha_t_stat: 2.74,
    residual_alpha: 0.018,
    threshold: 2.5,
  },
  rejection_reasons: [],
  paper_trading_only: true,
};

const PROD_HYPOTHESES_PAYLOAD = {
  run_date: "2026-07-27",
  hypotheses: {
    proposed: [
      {
        name: "back_to_back_fade",
        description: "Fade back-to-back teams.",
        predicted_direction: "no",
        required_inputs: ["schedule"],
      },
      {
        // No description / direction — still usable.
        name: "injury_overreaction",
        required_inputs: [],
      },
    ],
    verdicts: [
      {
        name: "back_to_back_fade",
        validator_factor: "mean_reversion",
        valid: true,
        reason: null,
      },
      {
        name: "injury_overreaction",
        validator_factor: "news_sentiment",
        valid: false,
        reason: "t-stat 1.21",
      },
    ],
    survivors: ["back_to_back_fade"],
    rejected: [{ name: "injury_overreaction", reason: "t-stat 1.21" }],
    factor_set: ["back_to_back_fade"],
    paper_trading_only: true,
  },
  rejection_reasons: [],
  paper_trading_only: true,
};

describe("alpha-runs-api client", () => {
  afterEach(() => resetAlphaRunsFetch());

  it("normalizes a live runs payload (prod {latest,runs} envelope)", async () => {
    setAlphaRunsFetch(jsonFetch(PROD_RUNS_PAYLOAD));

    const { data, source } = await getRuns();
    expect(source).toBe("live");
    expect(data.items).toHaveLength(2);
    expect(data.items[0]).toMatchObject({
      id: "bdb65fcb-d4cd-4ff5-b603-ea5f24053709",
      status: "no_signal",
      residual_alpha: null,
      t_stat: null,
      signal_emitted: false,
    });
    expect(data.items[0]?.started_at).toContain("2026-07-27");
    // Tolerant coercion: string residual parsed; genuine_edge → emitted.
    expect(data.items[1]?.residual_alpha).toBe(0.018);
    expect(data.items[1]?.t_stat).toBe(2.74);
    expect(data.items[1]?.signal_emitted).toBe(true);
    expect(data.paper_trading_only).toBe(true);
    expect(alphaRunStatusLabel(data.items[1]?.status ?? "")).toBe(
      "Edge confirmed",
    );
  });

  it("normalizes live latest-signal and hypotheses payloads (prod shapes)", async () => {
    setAlphaRunsFetch(jsonFetch(PROD_LATEST_SIGNAL_PAYLOAD));
    const withheld = await getLatestSignal();
    expect(withheld.source).toBe("live");
    expect(withheld.data.emitted).toBe(false);
    expect(withheld.data.t_stat).toBeNull();
    expect(withheld.data.created_at).toContain("2026-07-27");
    // Evidence comes from rejection_reasons when the signal is withheld.
    expect(withheld.data.evidence).toContain("oos_does_not_beat_closing");

    setAlphaRunsFetch(jsonFetch(PROD_EMITTED_SIGNAL_PAYLOAD));
    const emitted = await getLatestSignal();
    expect(emitted.source).toBe("live");
    expect(emitted.data.emitted).toBe(true);
    expect(emitted.data.t_stat).toBe(2.74);
    // Non-numeric weight entries are dropped, numeric ones survive.
    expect(emitted.data.weights).toEqual({ model_edge: 0.4, time_decay: 0.6 });

    setAlphaRunsFetch(jsonFetch(PROD_HYPOTHESES_PAYLOAD));
    const hypotheses = await getHypotheses();
    expect(hypotheses.source).toBe("live");
    expect(hypotheses.data.items).toHaveLength(2);
    expect(hypotheses.data.items[0]).toMatchObject({
      name: "back_to_back_fade",
      validated: true,
      reason: null,
    });
    expect(hypotheses.data.items[1]?.description).toBeNull();
    expect(hypotheses.data.items[1]?.reason).toBe("t-stat 1.21");

    // Empty-run shape `{signal: null, reason}` is a valid live envelope.
    setAlphaRunsFetch(
      jsonFetch({ signal: null, reason: "no_alpha_runs", paper_trading_only: true }),
    );
    const missing = await getLatestSignal();
    expect(missing.source).toBe("live");
    expect(missing.data.emitted).toBe(false);
    expect(missing.data.evidence).toBe("no_alpha_runs");
  });

  it("returns honest empty (not seed rows) when the live API is down", async () => {
    setAlphaRunsFetch(failingFetch);

    const runs = await getRuns();
    expect(runs.source).toBe("mock");
    expect(runs.data.paper_trading_only).toBe(true);
    expect(runs.data.items).toEqual([]);

    const signal = await getLatestSignal();
    expect(signal.source).toBe("mock");
    expect(signal.data.emitted).toBe(false);
    expect(signal.data.evidence).toBe("");
    expect(signal.data.residual_alpha).toBeNull();
    expect(signal.data.t_stat).toBeNull();

    const hypotheses = await getHypotheses();
    expect(hypotheses.source).toBe("mock");
    expect(hypotheses.data.items).toEqual([]);
  });

  it("rejects invented items/emitted envelopes (never treats them as live)", async () => {
    // The old wrong contract — must NOT normalize as live.
    setAlphaRunsFetch(
      jsonFetch({
        items: [
          {
            id: "run-fake",
            started_at: "2026-07-24T06:00:00Z",
            status: "genuine_edge",
            residual_alpha: 0.018,
            t_stat: 2.74,
            signal_emitted: true,
          },
        ],
        paper_trading_only: true,
      }),
    );
    const runs = await getRuns();
    expect(runs.source).toBe("mock");
    expect(runs.data.items).toEqual([]);

    setAlphaRunsFetch(
      jsonFetch({
        emitted: true,
        residual_alpha: 0.018,
        t_stat: 2.74,
        evidence: "fabricated",
      }),
    );
    const signal = await getLatestSignal();
    expect(signal.source).toBe("mock");
    expect(signal.data.emitted).toBe(false);
  });
});
