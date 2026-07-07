import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MARKETS, type Market } from "../lib/mock-data";
import { AIForecastPanel } from "./AIForecastPanel";
import { SimilarPastMarketsView } from "./SimilarPastMarkets";
import type { AgentMemoryRow } from "../lib/alphaedge-api";

// loop6 — the three new surfaces must each render when the backend supplies the
// field AND degrade silently (no error, no leftover chrome) when it is absent,
// so the frontend never breaks against an older backend.

function withForecast(extra: Partial<Market["forecast"]>): Market {
  const base = MARKETS[0];
  return { ...base, forecast: { ...base.forecast, ...extra } };
}

describe("Ensemble surface (AIForecastPanel)", () => {
  it("shows N models · ±stdev and spread warning when n_models > 1 and spread_flag", () => {
    const market = withForecast({
      nModels: 4,
      stdev: 0.18,
      spreadFlag: true,
      perModel: [
        { provider: "openai", prob: 0.61, rationale: "home form strong" },
        { provider: "anthropic", prob: 0.44, rationale: "injury risk" },
      ],
    });
    const html = renderToStaticMarkup(React.createElement(AIForecastPanel, { market }));

    expect(html).toContain("4 models");
    expect(html).toContain("±18.0pt");
    expect(html).toContain("high spread");
    expect(html).toContain("Per-model rationales (2)");
    expect(html).toContain("openai");
    expect(html).toContain("injury risk");
  });

  it("hides the ensemble badge and collapsible for a single-model / older backend", () => {
    const market = withForecast({}); // no nModels/perModel
    const html = renderToStaticMarkup(React.createElement(AIForecastPanel, { market }));

    expect(html).not.toContain("models");
    expect(html).not.toContain("high spread");
    expect(html).not.toContain("Per-model rationales");
    // Base panel still renders.
    expect(html).toContain("AI forecast");
  });

  it("omits the spread badge when models agree (spread_flag false)", () => {
    const market = withForecast({ nModels: 3, stdev: 0.04, spreadFlag: false });
    const html = renderToStaticMarkup(React.createElement(AIForecastPanel, { market }));

    expect(html).toContain("3 models");
    expect(html).not.toContain("high spread");
  });
});

describe("Tools surface (AIForecastPanel)", () => {
  it("renders tools_used as chips under the rationale when present", () => {
    const market = withForecast({ toolsUsed: ["spread", "whale_count"] });
    const html = renderToStaticMarkup(React.createElement(AIForecastPanel, { market }));

    expect(html).toContain("Tools");
    expect(html).toContain("spread");
    expect(html).toContain("whale_count");
  });

  it("renders no Tools row when tools_used is absent", () => {
    const html = renderToStaticMarkup(
      React.createElement(AIForecastPanel, { market: withForecast({}) }),
    );
    expect(html).not.toContain(">Tools<");
  });
});

describe("Memory surface (SimilarPastMarketsView)", () => {
  const rows: AgentMemoryRow[] = [
    {
      id: "m1",
      market_slug: "nba-2025-01-10-gsw-den",
      category: "Sports",
      question: "Will the Warriors beat the Nuggets?",
      outcome: "YES",
      model_prob_at_close: 0.62,
      market_prob_at_close: 0.55,
      brier: 0.1444,
      rationale_summary: "home court edge",
      created_at: "2026-01-11T00:00:00Z",
    },
  ];

  it("renders question, outcome, model-vs-market and Brier per row when memories exist", () => {
    const html = renderToStaticMarkup(
      React.createElement(SimilarPastMarketsView, { category: "Sports", rows }),
    );

    expect(html).toContain("Similar past markets");
    expect(html).toContain("Will the Warriors beat the Nuggets?");
    expect(html).toContain("YES");
    expect(html).toContain("model");
    expect(html).toContain("market");
    expect(html).toContain("0.1444");
  });

  it("renders nothing (no error) when there are no memories", () => {
    const html = renderToStaticMarkup(
      React.createElement(SimilarPastMarketsView, { category: "Sports", rows: [] }),
    );
    expect(html).toBe("");
  });
});
