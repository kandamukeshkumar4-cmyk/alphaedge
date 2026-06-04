import { isLockForecastMessage, isResolveMarketMessage } from "./messaging";
import { resolveExternalMarket, sendForecastToBackend } from "./backend-client";
import {
  enqueueForecast,
  idempotencyKeyFor,
  indexedDbForecastQueueStore,
  isReadyForRetry,
  retryDelayMs,
  syncQueuedForecasts,
} from "./queue";
import { getSettings } from "./storage";

let queueRetryTimer: number | undefined;

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (isResolveMarketMessage(message)) {
    void (async () => {
      try {
        const settings = await getSettings();
        const resolved = await resolveExternalMarket({
          apiBase: settings.apiBase,
          url: message.payload.url,
          title: message.payload.title,
        });
        sendResponse({ ok: true, data: resolved });
      } catch (error) {
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : "Market prefill failed.",
        });
      }
    })();
    return true;
  }

  if (!isLockForecastMessage(message)) {
    sendResponse({ ok: false, error: "Unsupported AlphaEdge Mirror message." });
    return;
  }

  void (async () => {
    try {
      const settings = await getSettings();
      const idempotencyKey = idempotencyKeyFor(message.payload);
      const result = await sendForecastToBackend({
        apiBase: settings.apiBase,
        message,
        idempotencyKey,
      });
      if (!result.ok) {
        if ((result.status ?? 0) >= 500) {
          const queued = await enqueueForecast(
            indexedDbForecastQueueStore,
            message,
            undefined,
            result.error,
          );
          scheduleQueueRetry();
          sendResponse({ ok: true, data: { queued: true, queueId: queued.id } });
          return;
        }
        sendResponse({ ok: false, error: result.error });
        return;
      }
      sendResponse({ ok: true, data: result.data });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Forecast lock failed.";
      const queued = await enqueueForecast(indexedDbForecastQueueStore, message, undefined, detail);
      scheduleQueueRetry();
      sendResponse({ ok: true, data: { queued: true, queueId: queued.id } });
    }
  })();

  return true;
});

scheduleQueueRetry();

function scheduleQueueRetry() {
  if (queueRetryTimer !== undefined) {
    return;
  }
  queueRetryTimer = setTimeout(() => {
    queueRetryTimer = undefined;
    void syncQueueOnce();
  }, 1_000) as unknown as number;
}

async function syncQueueOnce() {
  const settings = await getSettings();
  await syncQueuedForecasts(indexedDbForecastQueueStore, async (queued) => {
    try {
      const response = await sendForecastToBackend({
        apiBase: settings.apiBase,
        message: queued.message,
        idempotencyKey: queued.idempotencyKey,
      });
      if (!response.ok) {
        return { ok: false, error: response.error };
      }
      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        error: error instanceof Error ? error.message : "Sync failed.",
      };
    }
  });

  const rows = await indexedDbForecastQueueStore.loadQueue();
  const retryable = rows.filter((row) => row.status !== "synced");
  if (!retryable.length) {
    return;
  }
  const now = new Date();
  const ready = retryable.some((row) => isReadyForRetry(row, now));
  const nextDelay = ready ? 1_000 : Math.min(...retryable.map(delayUntilRetry));
  queueRetryTimer = setTimeout(() => {
    queueRetryTimer = undefined;
    void syncQueueOnce();
  }, Math.max(1_000, nextDelay)) as unknown as number;
}

function delayUntilRetry(row: { nextAttemptAt?: string; attempts: number }): number {
  if (!row.nextAttemptAt) {
    return retryDelayMs(row.attempts);
  }
  const timestamp = Date.parse(row.nextAttemptAt);
  if (!Number.isFinite(timestamp)) {
    return retryDelayMs(row.attempts);
  }
  return Math.max(1_000, timestamp - Date.now());
}
