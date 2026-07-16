import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LockedForecastPanelBody } from "./LockedForecastPanel";
import {
  buildLockedForecastView,
  PRE_LOCK_COPY,
  type LockedForecastResponse,
} from "@/lib/locked-forecast-api";

const NOW = Date.parse("2026-07-16T18:00:00Z");

const locked: LockedForecastResponse = {
  slug: "nba-2025-01-15-lal-bos",
  locked: true,
  user_probability: 0.62,
  locked_at: "2026-07-16T16:00:00Z",
  market_implied_at_lock: 0.55,
  current_market_probability: 0.58,
  mode: "live",
  provisional: true,
  paper_trading_only: true,
  forecast_id: "11111111-1111-1111-1111-111111111111",
  external_market_id: "22222222-2222-2222-2222-222222222222",
  empty_reason: null,
};

describe("LockedForecastPanelBody", () => {
  it("renders locked chip with probability, relative time, delta, and provisional", () => {
    const view = buildLockedForecastView(locked, { nowMs: NOW });
    const html = renderToStaticMarkup(
      React.createElement(LockedForecastPanelBody, { view }),
    );
    expect(html).toContain("data-testid=\"locked-forecast-panel\"");
    expect(html).toContain("62%");
    expect(html).toContain("2h ago");
    expect(html).toContain("58%");
    expect(html).toContain("+4 pts vs market");
    expect(html).toContain("PROVISIONAL");
    expect(html).toContain("Locked");
  });

  it("renders honest pre-lock empty state", () => {
    const view = buildLockedForecastView(
      {
        ...locked,
        locked: false,
        user_probability: null,
        locked_at: null,
        empty_reason: "pre_lock",
      },
      { nowMs: NOW },
    );
    const html = renderToStaticMarkup(
      React.createElement(LockedForecastPanelBody, { view }),
    );
    expect(html).toContain(PRE_LOCK_COPY);
    expect(html).not.toContain("Model: locked");
    expect(html).toContain("PROVISIONAL");
  });

  it("renders loading skeleton without inventing a probability", () => {
    const view = buildLockedForecastView(null, { loading: true });
    const html = renderToStaticMarkup(
      React.createElement(LockedForecastPanelBody, { view }),
    );
    expect(html).toContain("aria-busy=\"true\"");
    expect(html).not.toContain("%");
  });
});
