import { describe, expect, it } from "vitest";

import { lifecycleStateForMarket } from "./lifecycle";
import type { ParsedSupportedMarket } from "./platforms";

describe("forecast lifecycle state labels", () => {
  it("distinguishes no market, server snapshot, and manual snapshot states", () => {
    expect(lifecycleStateForMarket(null)).toEqual({
      state: "no_market_detected",
      label: "No supported market detected",
    });

    expect(lifecycleStateForMarket(market({ provider: "polymarket", manualOnly: false }))).toEqual({
      state: "api_snapshot_available",
      label: "Server API snapshot available",
    });

    expect(lifecycleStateForMarket(market({ provider: "fanduel", manualOnly: true }))).toEqual({
      state: "manual_snapshot_required",
      label: "Manual snapshot required",
    });
  });
});

function market(
  override: Partial<ParsedSupportedMarket> = {},
): ParsedSupportedMarket {
  return {
    platform: "polymarket",
    provider: "polymarket",
    externalId: "will-fed-cut-rates-in-july",
    canonicalUrl: "https://polymarket.com/event/will-fed-cut-rates-in-july",
    manualOnly: false,
    title: "Will the Fed cut rates in July?",
    ...override,
  };
}
