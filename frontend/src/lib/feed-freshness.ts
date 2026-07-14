import type { FeedItem } from "./feed-api";

const DEFAULT_DEDUPE_WINDOW_MS = 10 * 60 * 1000;

type NormalizeFeedOptions = {
  dedupeWindowMs?: number;
  limit?: number;
};

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function timestampMs(item: FeedItem): number {
  const parsed = Date.parse(item.timestamp);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
}

function semanticKey(item: FeedItem): string {
  const payload = record(item.payload);
  const detail = record(payload.detail);
  return [
    item.item_type,
    item.market_slug,
    item.platform ?? "",
    item.summary,
    item.confidence ?? "",
    item.target ?? "",
    payload.kind ?? "",
    payload.direction ?? "",
    payload.magnitude ?? "",
    detail.bps ?? "",
    payload.status ?? "",
    payload.horizon_minutes ?? "",
  ].join("|");
}

/** Sort newest-first and suppress repeated semantic items within a short window. */
export function normalizeFeedItems(
  items: FeedItem[],
  options: NormalizeFeedOptions = {},
): FeedItem[] {
  const windowMs = options.dedupeWindowMs ?? DEFAULT_DEDUPE_WINDOW_MS;
  const sorted = [...items].sort((left, right) => timestampMs(right) - timestampMs(left));
  const seenIds = new Set<string>();
  const lastKeptByKey = new Map<string, number>();
  const normalized: FeedItem[] = [];

  for (const item of sorted) {
    if (seenIds.has(item.id)) continue;
    seenIds.add(item.id);

    const createdMs = timestampMs(item);
    if (Number.isFinite(createdMs)) {
      const key = semanticKey(item);
      const newerMs = lastKeptByKey.get(key);
      if (newerMs !== undefined && newerMs - createdMs <= windowMs) continue;
      lastKeptByKey.set(key, createdMs);
    }

    normalized.push(item);
    if (options.limit !== undefined && normalized.length >= options.limit) break;
  }

  return normalized;
}
