import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  isCurrentMarketContextRequest,
  MarketContextPanel,
  MarketContextReady,
  MarketContextUnavailable,
} from "./MarketContextPanel";
import type { MarketContextResponse } from "@/lib/pods-api";

// Loop V60 (U4) — the market context panel must render its chrome and honest
// skeleton in the initial paint (effects/fetch never run during SSR), render
// the populated snapshot descriptively (no advice language, ever), and show
// honest absent states when the context endpoint is missing or unreachable.
describe("MarketContextPanel", () => {
  it("renders the panel header and endpoint caption in the initial paint", () => {
    const html = renderToStaticMarkup(
      React.createElement(MarketContextPanel, { slug: "nba-2025-01-15-lal-bos" }),
    );

    expect(html).toContain("Market context");
    expect(html).toContain("/api/v1/markets/");
    expect(html).toContain("/context");
  });

  it("shows skeleton rows (no fabricated metrics) before the fetch resolves", () => {
    const html = renderToStaticMarkup(
      React.createElement(MarketContextPanel, { slug: "nba-2025-01-15-lal-bos" }),
    );

    expect(html).toContain("skeleton");
    // No gauge, no populated values, no absent-state copy in the first paint.
    expect(html).not.toContain('role="meter"');
    expect(html).not.toContain("Venue gap");
    expect(html).not.toContain("not yet deployed");
    expect(html).not.toContain("captured");
  });
});

describe("MarketContextReady", () => {
  const context: MarketContextResponse = {
    whale_pressure: 0.72,
    venue_gap: 0.015,
    news_signal: 0.4,
    price_trend: 0.06,
    volume_pct: 0.81,
    captured_at: "2026-07-17T10:01:00Z",
  };

  it("renders the gauge, venue gap, news tone, trend, and volume descriptively", () => {
    const html = renderToStaticMarkup(React.createElement(MarketContextReady, { context }));

    expect(html).toContain("Whale pressure");
    expect(html).toContain('role="meter"');
    expect(html).toContain('aria-valuenow="72"');
    expect(html).toContain("heavy"); // 0.72 >= 0.67
    expect(html).toContain("Venue gap");
    expect(html).toContain("+1.5¢");
    expect(html).toContain("News tone");
    expect(html).toContain("positive");
    expect(html).toContain("+6.0%");
    expect(html).toContain("81%");
    expect(html).toContain("captured");
  });

  it("clamps an out-of-range whale reading at the gauge edges", () => {
    const html = renderToStaticMarkup(
      React.createElement(MarketContextReady, {
        context: { ...context, whale_pressure: 1.7 },
      }),
    );

    expect(html).toContain('aria-valuenow="100"');
  });

  it("never uses advice language — copy is descriptive only", () => {
    const html = renderToStaticMarkup(React.createElement(MarketContextReady, { context }));
    const lower = html.toLowerCase();

    expect(lower).not.toContain("you should");
    expect(lower).not.toContain("recommend");
    expect(lower).not.toContain("opportunity");
    expect(lower).not.toContain("good bet");
    expect(lower).not.toContain("place a trade");
    expect(lower).not.toContain("buy now");
    expect(lower).not.toContain("sell now");
    // The only "advice" mention allowed is the explicit disclaimer.
    expect(lower).toContain("not trading advice");
  });
});

describe("MarketContextUnavailable", () => {
  it("renders the honest not-deployed state for a 404", () => {
    const html = renderToStaticMarkup(
      React.createElement(MarketContextUnavailable, { reason: "not-deployed" }),
    );

    expect(html).toContain("Market context not yet deployed");
    expect(html).toContain("404");
    expect(html).toContain("nothing is mocked");
  });

  it("renders the honest unavailable state for other failures", () => {
    const html = renderToStaticMarkup(
      React.createElement(MarketContextUnavailable, { reason: "unavailable" }),
    );

    expect(html).toContain("Market context unavailable");
    expect(html).toContain("No cached or synthetic values");
  });
});

describe("isCurrentMarketContextRequest (loop71 stale guard)", () => {
  it("accepts the matching request id and drops stale ones", () => {
    expect(isCurrentMarketContextRequest(3, 3)).toBe(true);
    expect(isCurrentMarketContextRequest(2, 3)).toBe(false);
    expect(isCurrentMarketContextRequest(3, 4)).toBe(false);
  });
});
