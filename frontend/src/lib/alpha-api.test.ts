import { afterEach, describe, expect, it } from "vitest";

import {
  alphaRejectionLabel,
  fetchAlphaFactors,
  fetchAlphaReport,
  MOCK_ALPHA_REPORT,
  resetAlphaFetch,
  setAlphaFetch,
} from "@/lib/alpha-api";

function jsonFetch(payload: unknown, status = 200): typeof fetch {
  return (async () =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
}

const failingFetch = (async () =>
  new Response("nope", { status: 500 })) as typeof fetch;

describe("alpha-api client", () => {
  afterEach(() => resetAlphaFetch());

  it("normalizes a live factors payload (tolerant of missing fields)", async () => {
    setAlphaFetch(
      jsonFetch({
        market: "nba-2025-01-15-lal-bos",
        as_of: "2026-07-23T12:00:00Z",
        factors: [
          {
            name: "model_edge",
            score: 0.42,
            valid: true,
            t_stat: 2.31,
            reason: null,
            provenance: { available: true, fields: ["edge"] },
          },
          {
            // t_stat missing, score as string, no provenance — still usable.
            name: "momentum",
            score: "0.11",
            valid: false,
            reason: "oos_does_not_beat_closing",
          },
        ],
        rejected_factors: [{ name: "momentum", reason: "oos_does_not_beat_closing" }],
        paper_trading_only: true,
      }),
    );

    const { data, source } = await fetchAlphaFactors("nba-2025-01-15-lal-bos");
    expect(source).toBe("live");
    expect(data.market).toBe("nba-2025-01-15-lal-bos");
    expect(data.factors).toHaveLength(2);
    expect(data.factors[0]).toMatchObject({
      name: "model_edge",
      score: 0.42,
      valid: true,
      t_stat: 2.31,
    });
    // Tolerant coercion: string score parsed, missing t_stat → null.
    expect(data.factors[1]?.score).toBe(0.11);
    expect(data.factors[1]?.t_stat).toBeNull();
    expect(data.factors[1]?.provenance.available).toBe(true);
    expect(data.rejected_factors).toEqual([
      { name: "momentum", reason: "oos_does_not_beat_closing" },
    ]);
    expect(alphaRejectionLabel(data.factors[1]?.reason ?? null)).toBe(
      "Did not beat the closing line out-of-sample",
    );
  });

  it("falls back to the seeded paper mock when the live API is down", async () => {
    setAlphaFetch(failingFetch);

    const factors = await fetchAlphaFactors("nba-2025-01-15-lal-bos");
    expect(factors.source).toBe("mock");
    expect(factors.data.paper_trading_only).toBe(true);
    expect(factors.data.factors.map((f) => f.name)).toEqual([
      "model_edge",
      "time_decay",
      "whale_flow",
      "momentum",
      "cross_venue",
      "news_sentiment",
      "mean_reversion",
    ]);
    // Every killed factor carries a reason; every survivor has a t-stat.
    for (const factor of factors.data.factors) {
      if (factor.valid) expect(factor.t_stat).not.toBeNull();
      else expect(factor.reason).toBeTruthy();
    }

    const report = await fetchAlphaReport();
    expect(report.source).toBe("mock");
    expect(report.data.valid_factor_count).toBe(3);
    expect(report.data.valid_factor_count).toBe(
      MOCK_ALPHA_REPORT.factors.filter((f) => f.valid).length,
    );
    expect(report.data.rejected_factors.length).toBe(4);
  });
});
