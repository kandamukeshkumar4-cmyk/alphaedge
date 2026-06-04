import { describe, expect, it, vi } from "vitest";

import { recordMirrorTelemetryEvent } from "./backend-client";
import {
  buildMirrorTelemetryEvent,
  buildRecordTelemetryMessage,
  telemetryForLockResult,
  telemetryForParsedMarket,
  telemetryForParserMiss,
  telemetryForSyncedQueue,
  isRecordTelemetryMessage,
} from "./telemetry";
import type { ParsedSupportedMarket } from "./platforms";

describe("Mirror dogfood telemetry", () => {
  it("builds allowlisted event payloads without page content", () => {
    const event = buildMirrorTelemetryEvent({
      eventType: "market_detected",
      clientEventId: "evt-safe",
      platform: "polymarket",
      provider: "polymarket",
      captureMode: "server",
    });

    expect(event).toEqual({
      event_type: "market_detected",
      client_event_id: "evt-safe",
      platform: "polymarket",
      provider: "polymarket",
      capture_mode: "server",
    });
    expect(JSON.stringify(event)).not.toContain("https://polymarket.com/event");
    expect(JSON.stringify(event)).not.toContain("Will the Fed cut rates");
  });

  it("wraps telemetry in a single service-worker message type", () => {
    const message = buildRecordTelemetryMessage({
      eventType: "forecast_synced",
      clientEventId: "evt-synced",
      queueStatus: "synced",
    });

    expect(message.endpoint).toBe("/api/v1/telemetry/mirror/events");
    expect(isRecordTelemetryMessage(message)).toBe(true);
    expect(isRecordTelemetryMessage({ type: "ALPHAEDGE_LOCK_FORECAST" })).toBe(false);
  });

  it("sends telemetry through the AlphaEdge API with the token only in a header", async () => {
    const fetcher = vi.fn(async (_url: string, _init?: RequestInit) =>
      new Response(JSON.stringify({ ok: true, event_id: "event-id" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const event = buildMirrorTelemetryEvent({
      eventType: "dashboard_opened",
      clientEventId: "evt-dashboard",
    });

    await recordMirrorTelemetryEvent({
      apiBase: "https://api.example.test",
      token: "forecaster-token",
      event,
      fetcher,
    });

    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/telemetry/mirror/events",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "X-Forecaster-Token": "forecaster-token",
        },
        body: JSON.stringify(event),
      },
    );
    const init = fetcher.mock.calls[0][1] as RequestInit;
    expect(String(init.body)).not.toContain("forecaster-token");
  });

  it("maps parser and overlay lifecycle to safe telemetry events", () => {
    const detected = telemetryForParsedMarket(parsedMarket(), "server");
    const missed = telemetryForParserMiss();

    expect(detected).toEqual([
      expect.objectContaining({
        event_type: "market_detected",
        platform: "polymarket",
        provider: "polymarket",
        capture_mode: "server",
      }),
      expect.objectContaining({
        event_type: "overlay_opened",
        platform: "polymarket",
        provider: "polymarket",
        capture_mode: "server",
      }),
    ]);
    expect(missed).toMatchObject({ event_type: "parser_failed" });
    expect(JSON.stringify([...detected, missed])).not.toContain("url");
  });

  it("maps lock and queue sync outcomes to dogfood events", () => {
    expect(telemetryForLockResult("locked")).toMatchObject({
      event_type: "forecast_locked",
    });
    expect(telemetryForLockResult("queued")).toMatchObject({
      event_type: "forecast_queued",
      queue_status: "pending",
    });
    expect(telemetryForSyncedQueue(2)).toEqual([
      expect.objectContaining({
        event_type: "forecast_synced",
        queue_status: "synced",
      }),
      expect.objectContaining({
        event_type: "forecast_synced",
        queue_status: "synced",
      }),
    ]);
  });
});

function parsedMarket(): ParsedSupportedMarket {
  return {
    platform: "polymarket",
    provider: "polymarket",
    externalId: "will-fed-cut-rates",
    canonicalUrl: "https://polymarket.com/event/will-fed-cut-rates",
    manualOnly: false,
    title: "Will the Fed cut rates?",
  };
}
