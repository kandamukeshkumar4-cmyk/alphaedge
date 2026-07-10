import { describe, expect, it } from "vitest";
import {
  buildResolvedView,
  type ResolvedResponse,
  type ResolvedRow,
  type ResolvedSummary,
} from "./resolved-api";

function row(overrides: Partial<ResolvedRow>): ResolvedRow {
  return {
    slug: "mkt-a",
    title: "Market A",
    resolved_at: "2026-07-10T14:00:00+00:00",
    outcome: "YES",
    model_p_at_close: 0.62,
    correct: true,
    brier: 0.1444,
    ...overrides,
  };
}

function response(
  rows: ResolvedRow[],
  summary?: Partial<ResolvedSummary>,
): ResolvedResponse {
  return {
    rows,
    summary: {
      n: rows.length,
      accuracy: 0.75,
      mean_brier: 0.1225,
      thin_data: true,
      thin_data_threshold: 30,
      ...summary,
    },
    count: rows.length,
    limit: 50,
    offset: 0,
    paper_trading_only: true,
    signal_only: true,
    disclaimer: "Resolved-market review — NOT an order feed.",
    generated_at: "2026-07-10T18:00:00Z",
    cached: false,
  };
}

describe("buildResolvedView", () => {
  it("marks the view unreachable for a null response", () => {
    const view = buildResolvedView(null);
    expect(view.reachable).toBe(false);
    expect(view.rows).toEqual([]);
    expect(view.summary.n).toBe(0);
    expect(view.summary.accuracyLabel).toBe("—");
    expect(view.summary.meanBrierLabel).toBe("—");
    expect(view.summary.caveat).toBeNull();
  });

  it("is reachable but honest-empty when the page has no rows", () => {
    const view = buildResolvedView(
      response([], { n: 0, accuracy: null, mean_brier: null, thin_data: true }),
    );
    expect(view.reachable).toBe(true);
    expect(view.rows).toEqual([]);
    expect(view.summary.n).toBe(0);
    // No caveat at n=0 — nothing to caveat.
    expect(view.summary.caveat).toBeNull();
  });

  it("formats the summary header accuracy and mean Brier", () => {
    const view = buildResolvedView(
      response([row({})], { n: 4, accuracy: 0.75, mean_brier: 0.1225, thin_data: true }),
    );
    expect(view.summary.n).toBe(4);
    expect(view.summary.accuracyLabel).toBe("75%");
    expect(view.summary.meanBrierLabel).toBe("0.122");
  });

  it("emits a prominent small-sample caveat only when thin_data and n>0", () => {
    const thin = buildResolvedView(
      response([row({})], { n: 4, thin_data: true, thin_data_threshold: 30 }),
    );
    expect(thin.summary.caveat).toContain("Small sample (n=4)");
    expect(thin.summary.caveat).toContain("30");

    const thick = buildResolvedView(
      response([row({})], { n: 120, thin_data: false }),
    );
    expect(thick.summary.caveat).toBeNull();
  });

  it("builds a correct row with YES outcome and up tones", () => {
    const view = buildResolvedView(
      response([
        row({ slug: "y", outcome: "YES", model_p_at_close: 0.8, correct: true, brier: 0.04 }),
      ]),
    );
    const r = view.rows[0];
    expect(r.outcome).toBe("YES");
    expect(r.outcomeTone).toBe("up");
    expect(r.modelLabel).toBe("80%");
    expect(r.correct).toBe(true);
    expect(r.verdictLabel).toBe("Correct");
    expect(r.verdictTone).toBe("up");
    expect(r.brierLabel).toBe("0.040");
  });

  it("builds a missed row with NO outcome and down tones", () => {
    const view = buildResolvedView(
      response([
        row({ slug: "n", outcome: "NO", model_p_at_close: 0.6, correct: false, brier: 0.36 }),
      ]),
    );
    const r = view.rows[0];
    expect(r.outcome).toBe("NO");
    expect(r.outcomeTone).toBe("down");
    expect(r.verdictLabel).toBe("Missed");
    expect(r.verdictTone).toBe("down");
    expect(r.brierLabel).toBe("0.360");
  });

  it("renders an honest placeholder when resolved_at is null", () => {
    const view = buildResolvedView(response([row({ resolved_at: null })]));
    expect(view.rows[0].resolvedLabel).toBeNull();
  });

  it("degrades non-finite model probability / brier to placeholders without throwing", () => {
    const view = buildResolvedView(
      response([row({ model_p_at_close: Number.NaN, brier: Number.NaN })]),
    );
    expect(view.rows[0].modelLabel).toBe("—");
    expect(view.rows[0].brierLabel).toBe("—");
    expect(view.rows[0].brier).toBe(0);
  });

  it("preserves backend row order and passes through the cached flag", () => {
    const raw = response([row({ slug: "first" }), row({ slug: "second" })]);
    raw.cached = true;
    const view = buildResolvedView(raw);
    expect(view.rows.map((r) => r.slug)).toEqual(["first", "second"]);
    expect(view.cached).toBe(true);
  });

  it("uses the backend disclaimer when present", () => {
    const view = buildResolvedView(response([row({})]));
    expect(view.disclaimer).toContain("NOT an order feed");
  });
});
