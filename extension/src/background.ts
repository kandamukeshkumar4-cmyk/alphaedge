import { isLockForecastMessage } from "./messaging";
import { getSettings } from "./storage";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!isLockForecastMessage(message)) {
    sendResponse({ ok: false, error: "Unsupported AlphaEdge Mirror message." });
    return;
  }

  void (async () => {
    try {
      const settings = await getSettings();
      const response = await fetch(`${settings.apiBase}${message.endpoint}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(message.payload),
      });
      const data = (await response.json()) as unknown;
      if (!response.ok) {
        const detail =
          data && typeof data === "object" && "detail" in data
            ? String((data as { detail: unknown }).detail)
            : "Forecast lock failed.";
        sendResponse({ ok: false, error: detail });
        return;
      }
      sendResponse({ ok: true, data });
    } catch (error) {
      sendResponse({
        ok: false,
        error: error instanceof Error ? error.message : "Forecast lock failed.",
      });
    }
  })();

  return true;
});
