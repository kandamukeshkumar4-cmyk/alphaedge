import type { LockForecastMessage, LockForecastPayload } from "./messaging";

export type QueueStatus = "pending" | "syncing" | "synced" | "failed";

export type QueuedForecast = {
  id: string;
  idempotencyKey: string;
  status: QueueStatus;
  message: LockForecastMessage;
  lockedAt: string;
  updatedAt: string;
  attempts: number;
  lastError?: string;
};

export type ForecastQueueStore = {
  loadQueue: () => Promise<QueuedForecast[]>;
  saveQueue: (rows: QueuedForecast[]) => Promise<void>;
};

export type SyncResult = {
  synced: number;
  failed: number;
  pending: number;
};

export type SyncSender = (
  queued: QueuedForecast,
) => Promise<{ ok: true } | { ok: false; error: string }>;

const QUEUE_STORAGE_KEY = "forecastQueue";

export function idempotencyKeyFor(payload: LockForecastPayload): string {
  const stablePayload = stableStringify({
    url: payload.url,
    user_probability: payload.user_probability,
    market_implied_probability: payload.market_implied_probability,
    outcome_label: payload.outcome_label,
    market_title: payload.market_title ?? "",
    category: payload.category ?? "",
    mode: payload.mode,
    source: payload.source,
    token_hash: hash(payload.token),
  });
  return `aeq_${hash(stablePayload)}`;
}

export async function enqueueForecast(
  store: ForecastQueueStore,
  message: LockForecastMessage,
  lockedAt = new Date().toISOString(),
  lastError?: string,
): Promise<QueuedForecast> {
  const rows = await store.loadQueue();
  const idempotencyKey = idempotencyKeyFor(message.payload);
  const existing = rows.find((row) => row.idempotencyKey === idempotencyKey);
  if (existing) {
    return existing;
  }

  const queued: QueuedForecast = {
    id: idempotencyKey,
    idempotencyKey,
    status: "pending",
    message,
    lockedAt,
    updatedAt: lockedAt,
    attempts: 0,
    lastError,
  };
  await store.saveQueue([...rows, queued]);
  return queued;
}

export async function syncQueuedForecasts(
  store: ForecastQueueStore,
  sender: SyncSender,
): Promise<SyncResult> {
  const rows = await store.loadQueue();
  const nextRows = [...rows];
  let synced = 0;
  let failed = 0;

  for (const row of nextRows) {
    if (row.status === "synced" || row.status === "syncing") {
      continue;
    }

    row.status = "syncing";
    row.updatedAt = new Date().toISOString();
    row.attempts += 1;
    await store.saveQueue(nextRows);

    const result = await sender(row);
    row.updatedAt = new Date().toISOString();
    if (result.ok) {
      row.status = "synced";
      row.lastError = undefined;
      synced += 1;
    } else {
      row.status = "failed";
      row.lastError = result.error;
      failed += 1;
    }
    await store.saveQueue(nextRows);
  }

  return {
    synced,
    failed,
    pending: nextRows.filter((row) => row.status === "pending").length,
  };
}

export const chromeForecastQueueStore: ForecastQueueStore = {
  async loadQueue() {
    return new Promise((resolve) => {
      chrome.storage.local.get({ [QUEUE_STORAGE_KEY]: [] }, (items) => {
        resolve(Array.isArray(items[QUEUE_STORAGE_KEY]) ? items[QUEUE_STORAGE_KEY] : []);
      });
    });
  },
  async saveQueue(rows) {
    return new Promise((resolve) => {
      chrome.storage.local.set({ [QUEUE_STORAGE_KEY]: rows }, () => resolve());
    });
  },
};

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function hash(value: string): string {
  let result = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index);
    result = Math.imul(result, 0x01000193);
  }
  return (result >>> 0).toString(16).padStart(8, "0");
}
