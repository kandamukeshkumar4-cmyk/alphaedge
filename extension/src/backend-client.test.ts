import { describe, expect, it, vi } from "vitest";

import { buildLockForecastMessage } from "./messaging";
import { idempotencyKeyFor, type QueuedForecast } from "./queue";
import { fetchForecastLifecycle, sendForecastToBackend } from "./backend-client";

describe("backend client", () => {
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
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
