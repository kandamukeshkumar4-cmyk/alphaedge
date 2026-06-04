import { describe, expect, it } from "vitest";

import { buildLockForecastMessage } from "./messaging";
import {
  enqueueForecast,
  idempotencyKeyFor,
  retryDelayMs,
  isReadyForRetry,
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
    expect(queued.nextAttemptAt).toBeDefined();
    expect(queued.lockedAt).toBe("2026-06-04T15:00:00.000Z");
  });

  it("uses exponential backoff and does not retry before the next attempt time", async () => {
    const store = memoryStore();
    const message = sampleMessage();
    const now = new Date("2026-06-04T15:00:00.000Z");
    await enqueueForecast(store, message, now.toISOString());

    await syncQueuedForecasts(
      store,
      async () => ({ ok: false, error: "Backend unavailable" }),
      { now },
    );
    expect((await store.loadQueue())[0].nextAttemptAt).toBe(
      new Date(now.getTime() + retryDelayMs(1)).toISOString(),
    );

    const early = await syncQueuedForecasts(
      store,
      async () => ({ ok: true }),
      { now: new Date("2026-06-04T15:00:00.500Z") },
    );
    expect(early).toEqual({ synced: 0, failed: 0, pending: 0 });
    expect((await store.loadQueue())[0].status).toBe("failed");

    const late = await syncQueuedForecasts(
      store,
      async () => ({ ok: true }),
      { now: new Date("2026-06-04T15:00:01.000Z") },
    );
    expect(late).toEqual({ synced: 1, failed: 0, pending: 0 });
    expect((await store.loadQueue())[0].status).toBe("synced");
  });

  it("dedupes and syncs a 100-forecast offline stress batch exactly once", async () => {
    const store = memoryStore();
    for (let index = 0; index < 100; index += 1) {
      const message = sampleMessage(0.01 + index / 1_000);
      await enqueueForecast(store, message, `2026-06-04T15:${String(index).padStart(2, "0")}:00.000Z`);
      await enqueueForecast(store, message, `2026-06-04T15:${String(index).padStart(2, "0")}:01.000Z`);
    }

    const sent = new Set<string>();
    const result = await syncQueuedForecasts(store, async (queued) => {
      sent.add(queued.idempotencyKey);
      return { ok: true };
    });

    expect(await store.loadQueue()).toHaveLength(100);
    expect(sent.size).toBe(100);
    expect(result).toEqual({ synced: 100, failed: 0, pending: 0 });
    expect((await store.loadQueue()).every((row) => row.status === "synced")).toBe(true);
  });

  it("exposes retry readiness for the service worker scheduler", () => {
    const row = {
      ...queuedMessage(),
      nextAttemptAt: "2026-06-04T15:00:01.000Z",
    };

    expect(isReadyForRetry(row, new Date("2026-06-04T15:00:00.999Z"))).toBe(false);
    expect(isReadyForRetry(row, new Date("2026-06-04T15:00:01.000Z"))).toBe(true);
  });
});

function sampleMessage(userProbability = 0.64) {
  return buildLockForecastMessage({
    token: "forecaster-token",
    url: "https://polymarket.com/event/will-fed-cut-rates-in-july",
    userProbability,
    marketImpliedProbability: null,
    outcomeLabel: "YES",
    snapshotMetadata: { provider: "polymarket" },
  });
}

function queuedMessage(): QueuedForecast {
  const message = sampleMessage();
  return {
    id: "queue-row",
    idempotencyKey: idempotencyKeyFor(message.payload),
    status: "failed",
    message,
    lockedAt: "2026-06-04T15:00:00.000Z",
    updatedAt: "2026-06-04T15:00:00.000Z",
    attempts: 1,
  };
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
