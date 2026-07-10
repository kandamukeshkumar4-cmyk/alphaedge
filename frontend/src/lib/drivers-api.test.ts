import { describe, expect, it } from "vitest";
import { buildDriversView, type DriversResponse } from "./drivers-api";

function response(overrides: Partial<DriversResponse>): DriversResponse {
  return {
    found: true,
    slug: "nba-2025-01-15-lal-bos",
    model_p: 0.62,
    market_p: 0.5,
    gap: 0.12,
    drivers: [],
    paper_trading_only: true,
    signal_only: true,
    disclaimer: "Forecast drivers — signal only.",
    generated_at: "2026-07-10T18:00:00Z",
    ...overrides,
  };
}

describe("buildDriversView", () => {
  it("returns an honest not-found view for a null response", () => {
    const view = buildDriversView(null);
    expect(view.found).toBe(false);
    expect(view.hasDrivers).toBe(false);
    expect(view.gapLabel).toBeNull();
    expect(view.modelLabel).toBe("—");
  });

  it("returns an honest not-found view when the market is unknown", () => {
    const view = buildDriversView(response({ found: false, model_p: null, market_p: null, gap: null }));
    expect(view.found).toBe(false);
    expect(view.drivers).toEqual([]);
  });

  it("is found with empty drivers when a known market has none", () => {
    const view = buildDriversView(response({ drivers: [] }));
    expect(view.found).toBe(true);
    expect(view.hasDrivers).toBe(false);
  });

  it("formats the signed gap and model/market labels", () => {
    const view = buildDriversView(response({ model_p: 0.62, market_p: 0.5, gap: 0.12 }));
    expect(view.modelLabel).toBe("62%");
    expect(view.marketLabel).toBe("50%");
    expect(view.gapLabel).toBe("+12.0 pts");
    expect(view.gapTone).toBe("up");
  });

  it("shows a negative signed gap with a down tone", () => {
    const view = buildDriversView(response({ model_p: 0.4, market_p: 0.5, gap: -0.1 }));
    expect(view.gapLabel).toBe("-10.0 pts");
    expect(view.gapTone).toBe("down");
  });

  it("maps driver direction strings to for/against tones", () => {
    const view = buildDriversView(
      response({
        drivers: [
          { label: "Model vs market gap", direction: "favors YES", note: "gap", family: null, citation: null },
          { label: "Late scratch", direction: "favors NO", note: "news", family: "news:mispricing", citation: null },
          { label: "Quiet", direction: "neutral", note: "flat", family: null, citation: null },
        ],
      }),
    );
    expect(view.drivers.map((d) => d.directionTone)).toEqual(["up", "down", "neutral"]);
    expect(view.drivers[0].family).toBeNull();
    expect(view.drivers[1].family).toBe("news:mispricing");
  });

  it("builds news evidence from a signal driver citation", () => {
    const view = buildDriversView(
      response({
        drivers: [
          {
            label: "Star player questionable",
            direction: "favors YES",
            note: "news:mispricing signal",
            family: "news:mispricing",
            citation: {
              signal_id: "sig-1",
              news_id: null,
              news_url: "https://example.com/n1",
              headline: "Star player questionable",
              model_p: 0.62,
              market_p: 0.5,
            },
          },
        ],
      }),
    );
    const ev = view.drivers[0].evidence;
    expect(ev?.kind).toBe("news");
    if (ev?.kind === "news") {
      expect(ev.headline).toBe("Star player questionable");
      expect(ev.edgeLabel).toBe("+12.0 pts");
    }
  });

  it("keeps evidence null for the gap driver (no citation)", () => {
    const view = buildDriversView(
      response({
        drivers: [
          { label: "Model vs market gap", direction: "favors YES", note: "gap", family: null, citation: null },
        ],
      }),
    );
    expect(view.drivers[0].evidence).toBeNull();
  });
});
