import { describe, expect, it, vi } from "vitest";

import { fetchPaperSignalSummary, submitPaperSignal } from "./paper-signal-api";

describe("paper signal API", () => {
  it("loads persisted signal tallies for a market", async () => {
    const fetcher = vi.fn(async (url: string) => {
      expect(url).toBe("https://api.example.test/api/v1/markets/nba-2025-01-15-lal-bos/signals");
      return jsonResponse({
        paper_trading_only: true,
        market_id: "22222222-2222-2222-2222-222222222222",
        market_slug: "nba-2025-01-15-lal-bos",
        selected_outcome: null,
        total_signals: 2,
        options: [
          { outcome: "yes", count: 1, percentage: 50 },
          { outcome: "no", count: 1, percentage: 50 },
        ],
      });
    });

    const summary = await fetchPaperSignalSummary({
      apiBase: "https://api.example.test",
      fetcher,
      slug: "nba-2025-01-15-lal-bos",
    });

    expect(summary).toMatchObject({
      paper_trading_only: true,
      total_signals: 2,
      options: [
        { outcome: "yes", count: 1 },
        { outcome: "no", count: 1 },
      ],
    });
  });

  it("submits a signal through the system paper account", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/api/v1/paper-account")) {
        return jsonResponse({
          id: "00000000-0000-0000-0000-000000000001",
          name: "System Paper Account",
          cash_balance: "100000.0000",
          reserved_cash: "0.0000",
          available_cash: "100000.0000",
          paper_trading_only: true,
          positions: [],
          open_orders: [],
        });
      }
      if (url.endsWith("/api/v1/markets/nba-2025-01-15-lal-bos/signals")) {
        return jsonResponse({
          paper_trading_only: true,
          market_id: "22222222-2222-2222-2222-222222222222",
          market_slug: "nba-2025-01-15-lal-bos",
          selected_outcome: "yes",
          total_signals: 1,
          options: [
            { outcome: "yes", count: 1, percentage: 100 },
            { outcome: "no", count: 0, percentage: 0 },
          ],
        });
      }
      throw new Error(`Unexpected URL ${url}`);
    });

    const result = await submitPaperSignal({
      apiBase: "https://api.example.test",
      fetcher,
      slug: "nba-2025-01-15-lal-bos",
      outcome: "yes",
    });

    expect(result).toMatchObject({
      ok: true,
      mode: "api",
      summary: {
        selected_outcome: "yes",
        total_signals: 1,
      },
    });
    expect(calls[1].url).toBe(
      "https://api.example.test/api/v1/markets/nba-2025-01-15-lal-bos/signals",
    );
    expect(JSON.parse(String(calls[1].init?.body))).toEqual({
      account_id: "00000000-0000-0000-0000-000000000001",
      outcome: "yes",
    });
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
