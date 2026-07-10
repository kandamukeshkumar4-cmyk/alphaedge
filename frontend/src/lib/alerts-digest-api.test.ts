import { describe, expect, it } from "vitest";
import {
  buildAlertsDigestView,
  digestFamilyLabel,
  digestWindowLabel,
  type AlertsDigestResponse,
} from "./alerts-digest-api";

const NOW = Date.parse("2026-07-10T18:00:00Z");

const DIGEST: AlertsDigestResponse = {
  families: {
    "news:mispricing": 1,
    "delta:*": 3,
    arb: 1,
  },
  top_movers: [
    {
      slug: "nba-2025-01-15-lal-bos",
      signal_count: 3,
      families: { "delta:*": 2, "news:mispricing": 1 },
      last_signal_at: "2026-07-10T17:40:00Z",
    },
    {
      slug: "soccer-denmark-congo",
      signal_count: 2,
      families: { arb: 1, "delta:*": 1 },
      last_signal_at: "2026-07-10T15:00:00Z",
    },
  ],
  window: "24h",
  window_hours: 24,
  since: "2026-07-09T18:00:00Z",
  slugs: null,
  total: 5,
  paper_trading_only: true,
  disclaimer: "Alerts are notify/read only.",
};

describe("digestFamilyLabel", () => {
  it("labels every canonical L02 family", () => {
    expect(digestFamilyLabel("news:mispricing")).toBe("News mispricing");
    expect(digestFamilyLabel("anomaly:unusual_flow")).toBe("Unusual flow");
    expect(digestFamilyLabel("delta:*")).toBe("Price deltas");
    expect(digestFamilyLabel("screener:*")).toBe("Screener");
    expect(digestFamilyLabel("arb")).toBe("Arb");
  });

  it("humanises an unknown family key rather than throwing", () => {
    expect(digestFamilyLabel("weird:new_type")).toBe("weird · new type");
  });
});

describe("digestWindowLabel", () => {
  it("names the two toggle windows", () => {
    expect(digestWindowLabel("24h")).toBe("Last 24 hours");
    expect(digestWindowLabel("7d")).toBe("Last 7 days");
  });
});

describe("buildAlertsDigestView", () => {
  it("is unreachable on a null response", () => {
    const view = buildAlertsDigestView(null);
    expect(view.reachable).toBe(false);
    expect(view.empty).toBe(false);
    expect(view.familyRows).toHaveLength(0);
    expect(view.disclaimer.length).toBeGreaterThan(0);
  });

  it("sorts family rows by count desc then canonical order", () => {
    const view = buildAlertsDigestView(DIGEST, NOW);
    expect(view.reachable).toBe(true);
    expect(view.total).toBe(5);
    expect(view.familyRows.map((r) => r.key)).toEqual([
      "delta:*",
      "news:mispricing",
      "arb",
    ]);
    expect(view.familyRows[0]).toEqual({ key: "delta:*", label: "Price deltas", count: 3 });
  });

  it("drops zero/negative/non-finite family counts", () => {
    const view = buildAlertsDigestView({
      ...DIGEST,
      families: { "delta:*": 3, arb: 0, "screener:*": Number.NaN },
    });
    expect(view.familyRows.map((r) => r.key)).toEqual(["delta:*"]);
  });

  it("preserves backend mover order and humanises last-signal time", () => {
    const view = buildAlertsDigestView(DIGEST, NOW);
    expect(view.movers.map((m) => m.slug)).toEqual([
      "nba-2025-01-15-lal-bos",
      "soccer-denmark-congo",
    ]);
    expect(view.movers[0].signalCount).toBe(3);
    // Families within a mover are canonical-ordered.
    expect(view.movers[0].families).toEqual(["news:mispricing", "delta:*"]);
    expect(view.movers[0].lastLabel).toBe("20m ago");
  });

  it("is honestly empty when nothing fired in the window", () => {
    const view = buildAlertsDigestView({
      ...DIGEST,
      families: {},
      top_movers: [],
      total: 0,
    });
    expect(view.reachable).toBe(true);
    expect(view.empty).toBe(true);
    expect(view.familyRows).toHaveLength(0);
    expect(view.movers).toHaveLength(0);
  });

  it("derives total from family counts when the field is missing", () => {
    const { total, ...rest } = DIGEST;
    void total;
    const view = buildAlertsDigestView(rest);
    expect(view.total).toBe(5);
  });

  it("skips movers missing a slug", () => {
    const view = buildAlertsDigestView({
      ...DIGEST,
      top_movers: [{ signal_count: 9, families: { arb: 1 } }, DIGEST.top_movers![0]],
    });
    expect(view.movers.map((m) => m.slug)).toEqual(["nba-2025-01-15-lal-bos"]);
  });
});
