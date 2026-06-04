import { createRoot } from "react-dom/client";

import { MirrorOverlay } from "./overlay";
import { createOverlayHost, type OverlayDocument } from "./overlay-host";
import { buildResolveMarketMessage } from "../messaging";
import { parseSupportedUrl } from "../platforms";
import { prefillForMarket } from "../prefill";
import { getSettings } from "../storage";
import type { ExternalMarketResolveResponse } from "../backend-client";
import {
  buildRecordTelemetryMessage,
  telemetryForParsedMarket,
  telemetryForParserMiss,
  type MirrorTelemetryEvent,
} from "../telemetry";

export async function mountMirrorOverlay(input: {
  url: string;
  title: string;
  document: OverlayDocument;
}) {
  const parsed = parseSupportedUrl(input.url, input.title);
  if (!parsed) {
    sendTelemetry(telemetryForParserMiss());
    return;
  }

  const settings = await getSettings();
  const prefill = await prefillForMarket({
    market: parsed,
    apiBase: settings.apiBase,
    pageTitle: input.title,
    resolveMarket: resolveMarketThroughServiceWorker,
  });
  for (const event of telemetryForParsedMarket(parsed, prefill.source)) {
    sendTelemetry(event);
  }

  const { shadowRoot } = createOverlayHost(input.document);
  const mount = input.document.createElement("div") as unknown as HTMLElement;
  (shadowRoot as ShadowRoot).appendChild(mount);
  createRoot(mount).render(<MirrorOverlay market={parsed} prefill={prefill} />);
}

function sendTelemetry(event: MirrorTelemetryEvent) {
  chrome.runtime.sendMessage(buildRecordTelemetryMessage({
    eventType: event.event_type,
    clientEventId: event.client_event_id,
    platform: event.platform,
    provider: event.provider,
    captureMode: event.capture_mode,
    queueStatus: event.queue_status,
  }));
}

void mountMirrorOverlay({
  url: window.location.href,
  title: document.title,
  document: document as unknown as OverlayDocument,
});

function resolveMarketThroughServiceWorker(input: {
  url: string;
  title?: string;
}): Promise<ExternalMarketResolveResponse> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      buildResolveMarketMessage({ url: input.url, title: input.title }),
      (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message ?? "Market prefill failed."));
          return;
        }
        if (!response?.ok) {
          reject(new Error(response?.error ?? "Market prefill failed."));
          return;
        }
        resolve(response.data as ExternalMarketResolveResponse);
      },
    );
  });
}
