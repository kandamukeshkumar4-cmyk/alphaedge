import { isLockForecastMessage } from "./messaging";
import { sendForecastToBackend } from "./backend-client";
import { chromeForecastQueueStore, enqueueForecast, idempotencyKeyFor } from "./queue";
import { getSettings } from "./storage";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
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
            chromeForecastQueueStore,
            message,
            undefined,
            result.error,
          );
          sendResponse({ ok: true, data: { queued: true, queueId: queued.id } });
          return;
        }
        sendResponse({ ok: false, error: result.error });
        return;
      }
      sendResponse({ ok: true, data: result.data });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Forecast lock failed.";
      const queued = await enqueueForecast(chromeForecastQueueStore, message, undefined, detail);
      sendResponse({ ok: true, data: { queued: true, queueId: queued.id } });
    }
  })();

  return true;
});
