import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MARKETS, type Market } from "../lib/mock-data";
import { AIForecastPanel } from "./AIForecastPanel";
import { BriefEvidencePanel } from "./BriefEvidencePanel";
import { SimilarPastMarketsView } from "./SimilarPastMarkets";
import type { AnalystBrief } from "../lib/polyscout-api";
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

  it("renders honest empty when there are no memories", () => {
    const html = renderToStaticMarkup(
      React.createElement(SimilarPastMarketsView, {
        category: "Sports",
        rows: [],
        loaded: true,
      }),
    );
    expect(html).toContain("Similar past markets");
    expect(html).toContain("No agent memories yet");
    expect(html).not.toContain("Failed to fetch");
  });
});

describe("Brief evidence surface", () => {
  const baseBrief: AnalystBrief = {
    id: "b1",
    market_slug: "pm-bitcoin",
    headline: "Bitcoin moved",
    body_markdown: "Rationale",
    citations: [{ kind: "model", ref: "model p=0.630 edge=+0.025" }],
    model_version: "unknown",
    prompt_version: "v1",
    generator: "llm",
    kind: "brief",
    persona: null,
    latency_ms: 1200,
    created_at: "2026-07-08T17:48:09Z",
    claim: null,
  };

  it("renders model-vs-market metrics derived from the brief citation", () => {
    const html = renderToStaticMarkup(React.createElement(BriefEvidencePanel, { brief: baseBrief }));

    expect(html).toContain("Model vs market");
    expect(html).toContain("63.0%");
    expect(html).toContain("60.5%");
    expect(html).toContain("+2.5%");
  });

  it("renders ensemble and tools when optional payload fields are present", () => {
    const brief: AnalystBrief = {
      ...baseBrief,
      ensemble: {
        n_models: 3,
        stdev: 0.04,
        spread_flag: false,
        per_model: [{ provider: "primary:nim", prob: 0.52, rationale: "slight lean" }],
      },
      tools_used: [
        { tool: "get_order_book_summary", spread: 0.02 },
        { tool: "get_price_history", points: 50 },
      ],
    };
    const html = renderToStaticMarkup(React.createElement(BriefEvidencePanel, { brief }));

    expect(html).toContain("3 models");
    expect(html).toContain("±4.0pt");
    expect(html).toContain("Per-model rationales (1)");
    expect(html).toContain("get_order_book_summary spread 0.020");
    expect(html).toContain("get_price_history 50 pts");
  });

  it("renders nothing when no evidence fields are present", () => {
    const brief: AnalystBrief = { ...baseBrief, citations: [] };
    const html = renderToStaticMarkup(React.createElement(BriefEvidencePanel, { brief }));

    expect(html).toBe("");
  });
});
