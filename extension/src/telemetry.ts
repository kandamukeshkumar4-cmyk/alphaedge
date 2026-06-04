import type { ParsedSupportedMarket, SupportedPlatform, SupportedProvider } from "./platforms";

export type MirrorTelemetryEventType =
  | "overlay_opened"
  | "market_detected"
  | "parser_failed"
  | "forecast_locked"
  | "forecast_queued"
  | "forecast_synced"
  | "dashboard_opened";

export type MirrorTelemetryEvent = {
  event_type: MirrorTelemetryEventType;
  client_event_id: string;
  platform?: SupportedPlatform;
  provider?: SupportedProvider;
  capture_mode?: "server" | "manual" | "fallback";
  queue_status?: "pending" | "syncing" | "synced" | "failed";
};

export type RecordTelemetryMessage = {
  type: "ALPHAEDGE_RECORD_TELEMETRY";
  endpoint: "/api/v1/telemetry/mirror/events";
  payload: MirrorTelemetryEvent;
};

export function buildMirrorTelemetryEvent(input: {
  eventType: MirrorTelemetryEventType;
  clientEventId?: string;
  platform?: SupportedPlatform;
  provider?: SupportedProvider;
  captureMode?: "server" | "manual" | "fallback";
  queueStatus?: "pending" | "syncing" | "synced" | "failed";
}): MirrorTelemetryEvent {
  return {
    event_type: input.eventType,
    client_event_id: input.clientEventId ?? newClientEventId(),
    ...(input.platform ? { platform: input.platform } : {}),
    ...(input.provider ? { provider: input.provider } : {}),
    ...(input.captureMode ? { capture_mode: input.captureMode } : {}),
    ...(input.queueStatus ? { queue_status: input.queueStatus } : {}),
  };
}

export function buildRecordTelemetryMessage(input: Parameters<typeof buildMirrorTelemetryEvent>[0]) {
  return {
    type: "ALPHAEDGE_RECORD_TELEMETRY",
    endpoint: "/api/v1/telemetry/mirror/events",
    payload: buildMirrorTelemetryEvent(input),
  } satisfies RecordTelemetryMessage;
}

export function isRecordTelemetryMessage(value: unknown): value is RecordTelemetryMessage {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<RecordTelemetryMessage>;
  return (
    candidate.type === "ALPHAEDGE_RECORD_TELEMETRY" &&
    candidate.endpoint === "/api/v1/telemetry/mirror/events" &&
    Boolean(candidate.payload)
  );
}

export function telemetryForParserMiss(): MirrorTelemetryEvent {
  return buildMirrorTelemetryEvent({ eventType: "parser_failed" });
}

export function telemetryForParsedMarket(
  market: ParsedSupportedMarket,
  captureMode: "server" | "manual" | "fallback",
): MirrorTelemetryEvent[] {
  const common = {
    platform: market.platform,
    provider: market.provider,
    captureMode,
  };
  return [
    buildMirrorTelemetryEvent({ eventType: "market_detected", ...common }),
    buildMirrorTelemetryEvent({ eventType: "overlay_opened", ...common }),
  ];
}

export function telemetryForLockResult(status: "locked" | "queued"): MirrorTelemetryEvent {
  if (status === "queued") {
    return buildMirrorTelemetryEvent({
      eventType: "forecast_queued",
      queueStatus: "pending",
    });
  }
  return buildMirrorTelemetryEvent({ eventType: "forecast_locked" });
}

export function telemetryForSyncedQueue(count: number): MirrorTelemetryEvent[] {
  return Array.from({ length: Math.max(0, count) }, () =>
    buildMirrorTelemetryEvent({
      eventType: "forecast_synced",
      queueStatus: "synced",
    }),
  );
}

function newClientEventId(): string {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
