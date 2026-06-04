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
  nextAttemptAt?: string;
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
const INDEXED_DB_NAME = "alphaedge-mirror";
const INDEXED_DB_VERSION = 1;
const INDEXED_DB_STORE = "forecastQueue";
const BASE_RETRY_DELAY_MS = 1_000;
const MAX_RETRY_DELAY_MS = 5 * 60_000;

export function idempotencyKeyFor(payload: LockForecastPayload): string {
  const stablePayload = stableStringify({
    url: payload.url,
    user_probability: payload.user_probability,
    market_implied_probability: payload.market_implied_probability,
    outcome_label: payload.outcome_label,
    market_title: payload.market_title ?? "",
    category: payload.category ?? "",
    close_at: payload.close_at ?? "",
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
  options: { now?: Date } = {},
): Promise<SyncResult> {
  const rows = await store.loadQueue();
  const nextRows = [...rows];
  const now = options.now ?? new Date();
  let synced = 0;
  let failed = 0;

  for (const row of nextRows) {
    if (row.status === "synced" || row.status === "syncing") {
      continue;
    }
    if (!isReadyForRetry(row, now)) {
      continue;
    }

    row.status = "syncing";
    row.updatedAt = now.toISOString();
    row.attempts += 1;
    await store.saveQueue(nextRows);

    const result = await sender(row);
    row.updatedAt = new Date().toISOString();
    if (result.ok) {
      row.status = "synced";
      row.lastError = undefined;
      row.nextAttemptAt = undefined;
      synced += 1;
    } else {
      row.status = "failed";
      row.lastError = result.error;
      row.nextAttemptAt = new Date(now.getTime() + retryDelayMs(row.attempts)).toISOString();
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

export function createIndexedDbForecastQueueStore(dbFactory: IDBFactory): ForecastQueueStore {
  let dbPromise: Promise<IDBDatabase> | null = null;

  function db() {
    dbPromise ??= new Promise<IDBDatabase>((resolve, reject) => {
      const request = dbFactory.open(INDEXED_DB_NAME, INDEXED_DB_VERSION);
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains(INDEXED_DB_STORE)) {
          database.createObjectStore(INDEXED_DB_STORE, { keyPath: "id" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error ?? new Error("Could not open forecast queue."));
    });
    return dbPromise;
  }

  return {
    async loadQueue() {
      const database = await db();
      return new Promise<QueuedForecast[]>((resolve, reject) => {
        const request = database
          .transaction(INDEXED_DB_STORE, "readonly")
          .objectStore(INDEXED_DB_STORE)
          .getAll();
        request.onsuccess = () => resolve((request.result as QueuedForecast[]).sort(sortQueueRows));
        request.onerror = () => reject(request.error ?? new Error("Could not load forecast queue."));
      });
    },
    async saveQueue(rows) {
      const database = await db();
      return new Promise<void>((resolve, reject) => {
        const transaction = database.transaction(INDEXED_DB_STORE, "readwrite");
        const store = transaction.objectStore(INDEXED_DB_STORE);
        store.clear();
        for (const row of rows) {
          store.put(row);
        }
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error ?? new Error("Could not save forecast queue."));
      });
    },
  };
}

export const indexedDbForecastQueueStore: ForecastQueueStore = browserIndexedDb()
  ? createIndexedDbForecastQueueStore(browserIndexedDb()!)
  : chromeForecastQueueStore;

export function retryDelayMs(attempts: number): number {
  const exponent = Math.max(0, attempts - 1);
  return Math.min(BASE_RETRY_DELAY_MS * 2 ** exponent, MAX_RETRY_DELAY_MS);
}

export function isReadyForRetry(row: QueuedForecast, now = new Date()): boolean {
  if (!row.nextAttemptAt) {
    return true;
  }
  const timestamp = Date.parse(row.nextAttemptAt);
  return !Number.isFinite(timestamp) || timestamp <= now.getTime();
}

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

function browserIndexedDb(): IDBFactory | null {
  const scope = globalThis as typeof globalThis & { indexedDB?: IDBFactory };
  return scope.indexedDB ?? null;
}

function sortQueueRows(a: QueuedForecast, b: QueuedForecast): number {
  return a.lockedAt.localeCompare(b.lockedAt);
}
