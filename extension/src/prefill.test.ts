import { describe, expect, it, vi } from "vitest";

import { prefillForMarket } from "./prefill";
import type { ParsedSupportedMarket } from "./platforms";

describe("market prefill", () => {
  it("calls the server resolve-url adapter for Polymarket and keeps optional implied snapshots", async () => {
    const fetcher = vi.fn(async () =>
      jsonResponse({
        id: "market-id",
        platform: "polymarket",
        external_id: "will-fed-cut-rates",
        url: "https://polymarket.com/event/will-fed-cut-rates",
        title: "Will the Fed cut rates?",
        category: "Economics",
        status: "open",
        close_at: "2026-06-10T20:00:00Z",
        resolved_at: null,
        snapshot: {
          implied_probability: 0.57,
          source: "polymarket.gamma",
          metadata: { status: "active" },
        },
      }),
    );

    const prefill = await prefillForMarket({
      apiBase: "https://api.example.test",
      market: market({ provider: "polymarket", platform: "polymarket" }),
      fetcher,
    });

    expect(prefill).toMatchObject({
      title: "Will the Fed cut rates?",
      category: "Economics",
      closeAt: "2026-06-10T20:00:00Z",
      marketImpliedProbability: 0.57,
      source: "server",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/markets/external/resolve-url",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          url: "https://polymarket.com/event/will-fed-cut-rates",
          title: "Page title",
        }),
      }),
    );
  });

  it("calls the server resolve-url adapter for Kalshi and degrades when implied is absent", async () => {
    const fetcher = vi.fn(async () =>
      jsonResponse({
        id: "market-id",
        platform: "kalshi",
        external_id: "fed/fed-26jun",
        url: "https://kalshi.com/markets/fed/fed-26jun",
        title: "Fed decision",
        category: "Economics",
        status: "open",
        close_at: null,
        resolved_at: null,
      }),
    );

    const prefill = await prefillForMarket({
      apiBase: "https://api.example.test",
      market: market({ provider: "kalshi", platform: "kalshi" }),
      fetcher,
    });

    expect(prefill.title).toBe("Fed decision");
    expect(prefill.marketImpliedProbability).toBeNull();
    expect(prefill.snapshotSource).toBe("unavailable");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("keeps FanDuel manual-only and never calls the server for odds", async () => {
    const fetcher = vi.fn();

    const prefill = await prefillForMarket({
      apiBase: "https://api.example.test",
      market: market({ provider: "fanduel", platform: "manual", manualOnly: true }),
      fetcher,
    });

    expect(prefill).toMatchObject({
      title: "Page title",
      marketImpliedProbability: null,
      snapshotSource: "manual",
      source: "manual",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("falls back to URL-derived metadata when resolve-url misses", async () => {
    const fetcher = vi.fn(async () => jsonResponse({ detail: "not found" }, 400));

    const prefill = await prefillForMarket({
      apiBase: "https://api.example.test",
      market: market({ provider: "polymarket", platform: "polymarket" }),
      fetcher,
    });

    expect(prefill.source).toBe("fallback");
    expect(prefill.title).toBe("Page title");
    expect(prefill.marketImpliedProbability).toBeNull();
    expect(prefill.error).toBe("not found");
  });
});

function market(
  overrides: Partial<ParsedSupportedMarket> & Pick<ParsedSupportedMarket, "provider" | "platform">,
): ParsedSupportedMarket {
  const { provider, platform, ...rest } = overrides;
  return {
    provider,
    platform,
    externalId: provider === "kalshi" ? "fed/fed-26jun" : "will-fed-cut-rates",
    canonicalUrl:
      provider === "kalshi"
        ? "https://kalshi.com/markets/fed/fed-26jun"
        : "https://polymarket.com/event/will-fed-cut-rates",
    manualOnly: rest.manualOnly ?? false,
    title: "Page title",
    ...rest,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
