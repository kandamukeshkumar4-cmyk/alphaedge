import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AtlasAnalyzeReply } from "./AtlasAnalyzeReply";

const SAMPLE = `Paper-trade analysis for Lakers vs Celtics.
**Price:** YES ~54¢ (54.0%), volume $1,000.
**Model:** model 58.0% vs market 54.0% (edge +4.0%).
**Drivers:**
- Price Jump (favors YES): net +12¢
Analysis only — this assistant cannot place trades. Paper trading only — simulated funds, no execution.`;

describe("AtlasAnalyzeReply (Loop V77 A4)", () => {
  it("renders grouped section labels with paper-trading disclosure", () => {
    const html = renderToStaticMarkup(React.createElement(AtlasAnalyzeReply, { content: SAMPLE }));
    expect(html).toContain('data-atlas-analyze="sectioned"');
    expect(html).toContain("Price");
    expect(html).toContain("Model");
    expect(html).toContain("Drivers");
    expect(html).toContain("Analysis only");
    expect(html).toContain("Paper trading only");
    expect(html).not.toContain(">N/A<");
    expect(html.toLowerCase()).not.toContain("recommend");
  });

  it("falls back to lite markdown for plain chat replies", () => {
    const html = renderToStaticMarkup(
      React.createElement(AtlasAnalyzeReply, {
        content: "Ready to analyze paper markets.",
      }),
    );
    expect(html).not.toContain('data-atlas-analyze="sectioned"');
    expect(html).toContain("Ready to analyze");
  });
});
