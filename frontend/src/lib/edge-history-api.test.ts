import { describe, expect, it } from "vitest";
import {
  buildEdgeHistoryView,
  buildLinePath,
  type EdgeHistoryPoint,
  type EdgeHistoryResponse,
} from "./edge-history-api";

function response(series: EdgeHistoryPoint[], overrides?: Partial<EdgeHistoryResponse>): EdgeHistoryResponse {
  return {
    found: true,
    slug: "nba-2025-01-15-lal-bos",
    window: "7d",
    window_hours: 168,
    series,
    count: series.length,
    max_points: 200,
    paper_trading_only: true,
    signal_only: true,
    disclaimer: "Model-vs-market edge history — signal only.",
    generated_at: "2026-07-10T18:00:00Z",
    cached: false,
    ...overrides,
  };
}

describe("buildEdgeHistoryView", () => {
  it("returns an honest not-found view for a null response", () => {
    const view = buildEdgeHistoryView(null);
    expect(view.found).toBe(false);
    expect(view.available).toBe(false);
    expect(view.points).toEqual([]);
    expect(view.latest).toBeNull();
  });

  it("is found-but-not-available with a single point (no trend line)", () => {
    const view = buildEdgeHistoryView(
      response([{ t: "2026-07-10T14:00:00Z", model_p: 0.62, market_p: 0.5, edge: 0.12 }]),
    );
    expect(view.found).toBe(true);
    expect(view.available).toBe(false);
    expect(view.count).toBe(1);
  });

  it("builds an ordered two-point series with latest labels", () => {
    const view = buildEdgeHistoryView(
      response([
        { t: "2026-07-10T14:00:00Z", model_p: 0.62, market_p: 0.5, edge: 0.12 },
        { t: "2026-07-10T16:00:00Z", model_p: 0.7, market_p: 0.55, edge: 0.15 },
      ]),
    );
    expect(view.available).toBe(true);
    expect(view.hasMarketLine).toBe(true);
    expect(view.latest?.modelLabel).toBe("70%");
    expect(view.latest?.marketLabel).toBe("55%");
    expect(view.latest?.edgeLabel).toBe("+15.0 pts");
    expect(view.latest?.edgeTone).toBe("up");
  });

  it("derives a signed edge when the point omits it but has market_p", () => {
    const view = buildEdgeHistoryView(
      response([
        { t: "a", model_p: 0.4, market_p: 0.5, edge: null },
        { t: "b", model_p: 0.3, market_p: 0.5, edge: null },
      ]),
    );
    expect(view.points[0].edge).toBeCloseTo(-0.1);
    expect(view.latest?.edgeLabel).toBe("-20.0 pts");
    expect(view.latest?.edgeTone).toBe("down");
  });

  it("keeps market_p and edge null before the first snapshot", () => {
    const view = buildEdgeHistoryView(
      response([
        { t: "a", model_p: 0.6, market_p: null, edge: null },
        { t: "b", model_p: 0.62, market_p: 0.5, edge: 0.12 },
      ]),
    );
    expect(view.points[0].marketP).toBeNull();
    expect(view.points[0].edge).toBeNull();
    expect(view.hasMarketLine).toBe(true);
  });

  it("drops points with a non-finite model_p (never fabricated)", () => {
    const view = buildEdgeHistoryView(
      response([
        { t: "a", model_p: Number.NaN as unknown as number, market_p: 0.5, edge: null },
        { t: "b", model_p: 0.6, market_p: 0.5, edge: 0.1 },
      ]),
    );
    expect(view.count).toBe(1);
    expect(view.points[0].t).toBe("b");
  });
});

describe("buildLinePath", () => {
  const dims = { width: 300, height: 100, pad: 10 };

  it("returns an empty string when there is nothing drawable", () => {
    expect(buildLinePath([], dims)).toBe("");
    expect(buildLinePath([null, null], dims)).toBe("");
  });

  it("starts with a move then line commands across the width", () => {
    const d = buildLinePath([0, 1], dims);
    expect(d.startsWith("M")).toBe(true);
    expect(d).toContain("L");
    // y for v=0 is bottom (pad + innerH = 90); v=1 is top (pad = 10).
    expect(d).toContain("M10.00,90.00");
    expect(d).toContain("L290.00,10.00");
  });

  it("breaks the line on a null gap (new sub-path after the gap)", () => {
    const d = buildLinePath([0.5, null, 0.5], dims);
    // two M commands (line restarts) and no L bridging the gap.
    expect(d.match(/M/g)?.length).toBe(2);
    expect(d.includes("L")).toBe(false);
  });
});
