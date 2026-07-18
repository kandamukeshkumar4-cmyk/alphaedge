import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  DecisionLogTerminal,
  isCurrentDecisionPoll,
} from "./DecisionLogTerminal";

// Loop V60 (U3) — the decision-log terminal must render its chrome and honest
// skeleton rows in the initial paint (effects/fetch never run during SSR), and
// must never pre-render fabricated decision rows.
describe("DecisionLogTerminal", () => {
  it("renders the terminal header and endpoint caption in the initial paint", () => {
    const html = renderToStaticMarkup(React.createElement(DecisionLogTerminal));

    expect(html).toContain("Decision log");
    expect(html).toContain("/api/v1/heartbeat/decisions");
    expect(html).toContain("live · 5s poll"); // poll cadence label
  });

  it("shows skeleton rows (no fabricated decisions) before the first poll resolves", () => {
    const html = renderToStaticMarkup(React.createElement(DecisionLogTerminal));

    expect(html).toContain("skeleton");
    // No populated log, no empty-state copy, no error copy in the first paint.
    expect(html).not.toContain('role="log"');
    expect(html).not.toContain("No decisions logged yet");
    expect(html).not.toContain("not yet deployed");
  });
});

describe("isCurrentDecisionPoll (loop71 stale guard)", () => {
  it("accepts the matching poll id and drops out-of-order responses", () => {
    expect(isCurrentDecisionPoll(5, 5)).toBe(true);
    expect(isCurrentDecisionPoll(4, 5)).toBe(false);
    expect(isCurrentDecisionPoll(5, 6)).toBe(false);
  });
});
