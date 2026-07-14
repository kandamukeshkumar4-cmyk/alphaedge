import type { SignalEventItem } from "./activity-api";
import type { Market } from "./mock-data";

export type SignalRailDirection = "UP" | "DOWN" | "INFO";

export type SignalRailRow = {
  key: string;
  slug: string;
  title: string;
  direction: SignalRailDirection;
  label: string;
  value: string;
  age: string;
};

type BuildSignalRailOptions = {
  limit?: number;
  nowMs?: number;
  dedupeWindowMs?: number;
  maxAgeMs?: number;
};

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function directionOf(payload: Record<string, unknown>): SignalRailDirection {
  const raw = typeof payload.direction === "string" ? payload.direction.toLowerCase() : "";
  if (["up", "buy", "long", "positive"].includes(raw)) return "UP";
  if (["down", "sell", "short", "negative"].includes(raw)) return "DOWN";
  return "INFO";
}

function signed(value: number, direction: SignalRailDirection): number {
  if (direction === "UP") return Math.abs(value);
  if (direction === "DOWN") return -Math.abs(value);
  return value;
}

function signedLabel(value: number, suffix: string): string {
  const rounded = Math.abs(value) >= 100 || Number.isInteger(value)
    ? value.toFixed(0)
    : value.toFixed(1);
  return `${value > 0 ? "+" : ""}${rounded}${suffix}`;
}

function magnitudeLabel(payload: Record<string, unknown>, direction: SignalRailDirection): string {
  const detail = record(payload.detail);
  const bps = finiteNumber(detail.bps) ?? finiteNumber(payload.move_bps);
  if (bps !== null) return signedLabel(signed(bps, direction), " bps");

  const magnitude = finiteNumber(payload.magnitude);
  if (magnitude !== null) {
    if (Math.abs(magnitude) <= 1) {
      return signedLabel(signed(magnitude * 100, direction), "¢");
    }
    return signedLabel(signed(magnitude, direction), "");
  }

  for (const key of ["score", "confidence", "edge"] as const) {
    const value = finiteNumber(payload[key]);
    if (value !== null) return `${key} ${value.toFixed(2)}`;
  }
  return "Observed";
}

function signalLabel(signalType: string): string {
  const raw = signalType.includes(":") ? signalType.split(":").at(-1)! : signalType;
  return raw
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function titleFromSlug(slug: string): string {
  return slug
    .replace(/^(pm|ks)-/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function relativeSignalAge(createdAt: string, nowMs = Date.now()): string {
  const createdMs = Date.parse(createdAt);
  if (!Number.isFinite(createdMs)) return "time unknown";
  const seconds = Math.max(0, Math.floor((nowMs - createdMs) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function semanticKey(event: SignalEventItem): string {
  const payload = record(event.payload);
  const detail = record(payload.detail);
  return [
    event.market_id,
    event.signal_type,
    payload.kind ?? "",
    payload.direction ?? "",
    payload.magnitude ?? "",
    detail.bps ?? "",
  ].join("|");
}

export function dedupeSignalEvents(
  events: SignalEventItem[],
  windowMs = 10 * 60 * 1000,
): SignalEventItem[] {
  const newestByKey = new Map<string, number>();
  return [...events]
    .sort((left, right) => {
      const leftMs = Date.parse(left.created_at);
      const rightMs = Date.parse(right.created_at);
      return (Number.isFinite(rightMs) ? rightMs : -Infinity)
        - (Number.isFinite(leftMs) ? leftMs : -Infinity);
    })
    .filter((event) => {
    const createdMs = Date.parse(event.created_at);
    if (!Number.isFinite(createdMs)) return true;
    const key = semanticKey(event);
    const newerMs = newestByKey.get(key);
    if (newerMs !== undefined && newerMs - createdMs <= windowMs) return false;
    newestByKey.set(key, createdMs);
    return true;
    });
}

export function tickerFreshnessWindowMs(rawHours?: string): number {
  const hours = Number(rawHours);
  return Number.isFinite(hours) && hours > 0
    ? hours * 60 * 60 * 1000
    : 48 * 60 * 60 * 1000;
}

export function buildSignalRailRows(
  events: SignalEventItem[],
  markets: Market[],
  options: BuildSignalRailOptions = {},
): SignalRailRow[] {
  const bySlug = new Map(markets.map((market) => [market.slug, market]));
  const limit = options.limit ?? 5;
  const nowMs = options.nowMs ?? Date.now();
  const deduped = dedupeSignalEvents(events, options.dedupeWindowMs);
  const fresh = options.maxAgeMs === undefined
    ? deduped
    : deduped.filter((event) => {
        const createdMs = Date.parse(event.created_at);
        return Number.isFinite(createdMs) && nowMs - createdMs <= options.maxAgeMs!;
      });
  return fresh.slice(0, limit).map((event) => {
    const payload = record(event.payload);
    const direction = directionOf(payload);
    return {
      key: event.id,
      slug: event.market_id,
      title:
        event.market_title?.trim() ||
        bySlug.get(event.market_id)?.title ||
        titleFromSlug(event.market_id),
      direction,
      label: signalLabel(event.signal_type),
      value: magnitudeLabel(payload, direction),
      age: relativeSignalAge(event.created_at, nowMs),
    };
  });
}
