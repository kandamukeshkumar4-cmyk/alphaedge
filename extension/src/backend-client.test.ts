import { describe, expect, it, vi } from "vitest";

import { buildLockForecastMessage } from "./messaging";
import { idempotencyKeyFor, type QueuedForecast } from "./queue";
import {
  createAnonymousForecaster,
  fetchForecastDashboard,
  fetchForecastLifecycle,
  recoverForecaster,
  resolveExternalMarket,
  sendForecastToBackend,
} from "./backend-client";

describe("backend client", () => {
  it("creates an anonymous profile with a separate recovery code", async () => {
    const fetcher = vi.fn(async () =>
      jsonResponse({
        id: "forecaster-id",
        token: "forecaster-token",
        recovery_code: "recovery-code",
        disclaimer: "Paper simulation only.",
      }),
    );

    const profile = await createAnonymousForecaster({
      apiBase: "https://api.example.test",
      fetcher,
    });

    expect(profile).toMatchObject({
      token: "forecaster-token",
      recovery_code: "recovery-code",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/forecasters/anonymous",
      { method: "POST" },
    );
  });

  it("recovers a lost profile token with a recovery code", async () => {
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) =>
      jsonResponse({
        id: "forecaster-id",
        token: "new-token",
        recovery_code: "new-recovery-code",
        disclaimer: "Paper simulation only.",
      }),
    );

    const profile = await recoverForecaster({
      apiBase: "https://api.example.test",
      recoveryCode: "old-recovery-code",
      fetcher,
    });

    expect(profile).toMatchObject({
      token: "new-token",
      recovery_code: "new-recovery-code",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/forecasters/recover",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ recovery_code: "old-recovery-code" }),
      },
    );
    expect(JSON.stringify(fetcher.mock.calls[0][1])).not.toContain("new-token");
  });

  it("sends queued forecast idempotency keys to the backend", async () => {
    const message = buildLockForecastMessage({
      token: "forecaster-token",
      url: "https://polymarket.com/event/will-fed-cut-rates-in-july",
      userProbability: 0.64,
      marketImpliedProbability: null,
      outcomeLabel: "YES",
      snapshotMetadata: { provider: "polymarket" },
    });
    const queued: QueuedForecast = {
      id: "queue-row",
      idempotencyKey: idempotencyKeyFor(message.payload),
      status: "pending",
      message,
      lockedAt: "2026-06-04T15:00:00.000Z",
      updatedAt: "2026-06-04T15:00:00.000Z",
      attempts: 0,
    };
    const fetcher = vi.fn(async () => jsonResponse({ id: "forecast-id" }));

    const result = await sendForecastToBackend({
      apiBase: "https://api.example.test",
      message,
      idempotencyKey: queued.idempotencyKey,
      fetcher,
    });

    expect(result.ok).toBe(true);
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/forecasts",
      expect.objectContaining({
        method: "POST",
        headers: {
          "content-type": "application/json",
          "Idempotency-Key": queued.idempotencyKey,
        },
      }),
    );
  });

  it("fetches lifecycle counts without exposing token values", async () => {
    const fetcher = vi.fn(async () =>
      jsonResponse({
        unresolved_count: 2,
        recently_resolved_count: 1,
        unresolved: [],
        recently_resolved: [],
      }),
    );

    const lifecycle = await fetchForecastLifecycle({
      apiBase: "https://api.example.test",
      token: "secret-token",
      fetcher,
    });

    expect(lifecycle).toMatchObject({
      unresolved_count: 2,
      recently_resolved_count: 1,
    });
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/forecasters/me/forecast-lifecycle",
      {
        headers: {
          "X-Forecaster-Token": "secret-token",
        },
      },
    );
  });

  it("resolves external markets through the AlphaEdge API", async () => {
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

    const market = await resolveExternalMarket({
      apiBase: "https://api.example.test",
      url: "https://kalshi.com/markets/fed/fed-26jun",
      title: "Fed decision",
      fetcher,
    });

    expect(market.title).toBe("Fed decision");
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/markets/external/resolve-url",
      expect.objectContaining({
        method: "POST",
        headers: { "content-type": "application/json" },
      }),
    );
  });

  it("fetches compact dashboard metrics for the popup", async () => {
    const fetcher = vi.fn(async () =>
      jsonResponse({
        paper_trading_only: true,
        live: {
          resolved_count: 10,
          unresolved_count: 2,
          independent_count: 8,
          anchored_count: 1,
          mean_user_brier: 0.22,
          mean_brier_delta: 0.04,
          synthetic_pnl_total: 1.2,
        },
      }),
    );

    const dashboard = await fetchForecastDashboard({
      apiBase: "https://api.example.test",
      token: "secret-token",
      fetcher,
    });

    expect(dashboard.live.independent_count).toBe(8);
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/forecasters/me/dashboard",
      {
        cache: "no-store",
        headers: {
          "X-Forecaster-Token": "secret-token",
        },
      },
    );
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
