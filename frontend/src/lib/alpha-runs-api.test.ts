import { afterEach, describe, expect, it } from "vitest";

import {
  alphaRunStatusLabel,
  getHypotheses,
  getLatestSignal,
  getRuns,
  MOCK_ALPHA_RUNS,
  MOCK_HYPOTHESES,
  MOCK_LATEST_SIGNAL,
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

describe("alpha-runs-api client", () => {
  afterEach(() => resetAlphaRunsFetch());

  it("normalizes a live runs payload (tolerant of missing fields)", async () => {
    setAlphaRunsFetch(
      jsonFetch({
        items: [
          {
            id: "run-2026-07-24",
            started_at: "2026-07-24T06:00:00Z",
            finished_at: "2026-07-24T06:05:12Z",
            status: "genuine_edge",
            residual_alpha: 0.018,
            t_stat: 2.74,
            signal_emitted: true,
          },
          {
            // residual_alpha as string, no t_stat / finished_at / id —
            // still usable.
            started_at: "2026-07-23T06:00:00Z",
            status: "no_signal",
            residual_alpha: "0.004",
            signal_emitted: false,
          },
        ],
        paper_trading_only: true,
      }),
    );

    const { data, source } = await getRuns();
    expect(source).toBe("live");
    expect(data.items).toHaveLength(2);
    expect(data.items[0]).toMatchObject({
      id: "run-2026-07-24",
      status: "genuine_edge",
      residual_alpha: 0.018,
      t_stat: 2.74,
      signal_emitted: true,
    });
    // Tolerant coercion: string residual parsed, missing t_stat → null.
    expect(data.items[1]?.residual_alpha).toBe(0.004);
    expect(data.items[1]?.t_stat).toBeNull();
    expect(data.items[1]?.finished_at).toBeNull();
    expect(data.paper_trading_only).toBe(true);
    expect(alphaRunStatusLabel(data.items[0]?.status ?? "")).toBe(
      "Edge confirmed",
    );
  });

  it("normalizes live latest-signal and hypotheses payloads", async () => {
    setAlphaRunsFetch(
      jsonFetch({
        emitted: true,
        residual_alpha: 0.018,
        t_stat: 2.74,
        evidence: "Residual alpha beats the closing line out-of-sample.",
        weights: { model_edge: 0.4, time_decay: 0.6, bad_entry: "junk" },
        created_at: "2026-07-23T06:04:47Z",
      }),
    );
    const signal = await getLatestSignal();
    expect(signal.source).toBe("live");
    expect(signal.data.emitted).toBe(true);
    expect(signal.data.t_stat).toBe(2.74);
    // Non-numeric weight entries are dropped, numeric ones survive.
    expect(signal.data.weights).toEqual({ model_edge: 0.4, time_decay: 0.6 });

    setAlphaRunsFetch(
      jsonFetch({
        items: [
          {
            name: "back_to_back_fade",
            description: "Fade back-to-back teams.",
            predicted_direction: "no",
            validated: true,
            reason: null,
          },
          // No description / direction / reason — still usable.
          { name: "injury_overreaction", validated: false, reason: "t-stat 1.21" },
        ],
      }),
    );
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

    // A payload without `emitted` is not a signal shape → mock fallback.
    setAlphaRunsFetch(jsonFetch({ signal: null, reason: "no_alpha_runs" }));
    const missing = await getLatestSignal();
    expect(missing.source).toBe("mock");
    expect(typeof missing.data.emitted).toBe("boolean");
  });

  it("falls back to the seeded paper mock when the live API is down", async () => {
    setAlphaRunsFetch(failingFetch);

    const runs = await getRuns();
    expect(runs.source).toBe("mock");
    expect(runs.data.paper_trading_only).toBe(true);
    expect(runs.data.items.length).toBe(MOCK_ALPHA_RUNS.items.length);
    // Signal flag is consistent with the status, and emitted runs carry a
    // t-stat.
    for (const run of runs.data.items) {
      if (run.signal_emitted) {
        expect(run.status).toBe("genuine_edge");
        expect(run.t_stat).not.toBeNull();
      }
    }

    const signal = await getLatestSignal();
    expect(signal.source).toBe("mock");
    expect(signal.data.emitted).toBe(false);
    // A withheld signal always explains why (evidence is never empty).
    expect(signal.data.evidence.length).toBeGreaterThan(0);
    expect(signal.data.evidence).toBe(MOCK_LATEST_SIGNAL.evidence);

    const hypotheses = await getHypotheses();
    expect(hypotheses.source).toBe("mock");
    expect(hypotheses.data.items.length).toBe(MOCK_HYPOTHESES.items.length);
    // Rejected proposals carry a reason; validated ones do not.
    for (const h of hypotheses.data.items) {
      if (h.validated) expect(h.reason).toBeNull();
      else expect(h.reason).toBeTruthy();
    }
  });
});
