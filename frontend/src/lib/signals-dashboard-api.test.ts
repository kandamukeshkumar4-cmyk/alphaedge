import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchSignalsDashboard } from "./signals-dashboard-api";

describe("fetchSignalsDashboard", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("fetches same-origin when apiBase is empty (Vercel rewrite)", async () => {
    // Mirror browser production: empty base + hasLiveApi(true) via window + production.
    vi.stubEnv("NODE_ENV", "production");
    vi.stubGlobal("window", {} as Window & typeof globalThis);

    const fetcher = vi.fn(async () =>
      Response.json({
        paper_trading_only: true,
        disclaimer: "Paper trading only.",
        signals: [
          {
            id: "sig-1",
            signal_type: "delta:price_jump",
            platform: "polymarket",
            market_id: "pm-test",
            market_name: "Test market",
            implied_edge: null,
            sample_size: 0,
            is_edge: false,
            provisional: true,
            created_at: "2026-07-09T00:00:00Z",
            resolved: false,
          },
        ],
        clv_records: [],
        paper_pnl: {
          total_pnl: 0,
          n_bets: 0,
          win_rate: 0,
          note: "paper-only",
          disclaimer: "Paper trading only.",
          paper_trading_only: true,
        },
        llm_explanation: null,
      }),
    );

    const dashboard = await fetchSignalsDashboard({ apiBase: "", fetcher });

    expect(fetcher).toHaveBeenCalledWith("/api/v1/signals/dashboard", {
      cache: "no-store",
    });
    expect(dashboard?.signals).toHaveLength(1);
  });
});
