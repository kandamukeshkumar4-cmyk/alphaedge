import { describe, expect, it } from "vitest";

import { buildLockForecastMessage } from "./messaging";
import {
  enqueueForecast,
  idempotencyKeyFor,
  syncQueuedForecasts,
  type ForecastQueueStore,
  type QueuedForecast,
} from "./queue";

describe("offline forecast queue", () => {
  it("stores unavailable backend submissions as pending with a stable idempotency key", async () => {
    const store = memoryStore();
    const message = sampleMessage();

    const queued = await enqueueForecast(store, message, "2026-06-04T15:00:00.000Z");
    const duplicate = await enqueueForecast(store, message, "2026-06-04T15:00:01.000Z");

    expect(queued.status).toBe("pending");
    expect(queued.idempotencyKey).toBe(idempotencyKeyFor(message.payload));
    expect(duplicate.id).toBe(queued.id);
    expect(await store.loadQueue()).toHaveLength(1);
  });

  it("syncs each queued forecast exactly once and marks successful rows synced", async () => {
    const store = memoryStore();
    const message = sampleMessage();
    await enqueueForecast(store, message, "2026-06-04T15:00:00.000Z");
    const sent: string[] = [];

    const result = await syncQueuedForecasts(store, async (queued) => {
      sent.push(queued.idempotencyKey);
      return { ok: true };
    });
    const second = await syncQueuedForecasts(store, async (queued) => {
      sent.push(queued.idempotencyKey);
      return { ok: true };
    });

    expect(result).toEqual({ synced: 1, failed: 0, pending: 0 });
    expect(second).toEqual({ synced: 0, failed: 0, pending: 0 });
    expect(sent).toEqual([idempotencyKeyFor(message.payload)]);
    expect((await store.loadQueue())[0].status).toBe("synced");
  });

  it("marks failed retries failed without dropping the local receipt", async () => {
    const store = memoryStore();
    const message = sampleMessage();
    await enqueueForecast(store, message, "2026-06-04T15:00:00.000Z");

    const result = await syncQueuedForecasts(store, async () => ({
      ok: false,
      error: "Backend unavailable",
    }));
    const [queued] = await store.loadQueue();

    expect(result).toEqual({ synced: 0, failed: 1, pending: 0 });
    expect(queued.status).toBe("failed");
    expect(queued.lastError).toBe("Backend unavailable");
    expect(queued.lockedAt).toBe("2026-06-04T15:00:00.000Z");
  });
});

function sampleMessage() {
  return buildLockForecastMessage({
    token: "forecaster-token",
    url: "https://polymarket.com/event/will-fed-cut-rates-in-july",
    userProbability: 0.64,
    marketImpliedProbability: null,
    outcomeLabel: "YES",
    snapshotMetadata: { provider: "polymarket" },
  });
}

function memoryStore(initial: QueuedForecast[] = []): ForecastQueueStore {
  let rows = initial;
  return {
    async loadQueue() {
      return rows;
    },
    async saveQueue(nextRows) {
      rows = nextRows;
    },
  };
}
