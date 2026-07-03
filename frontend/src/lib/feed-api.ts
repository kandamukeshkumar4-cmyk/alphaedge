/**
 * U02 — Unified activity feed API client.
 * Talks to GET /api/v1/feed (backend feed.py).
 */
import { API_BASE, WS_BASE } from "./alphaedge-api";

export type FeedItemType =
  | "alignment"
  | "whale_delta"
  | "instability_shift"
  | "news_arrival"
  | "brief"
  | "digest"
  | "claim_graded"
  | "signal";

export interface FeedItem {
  id: string;
  item_type: FeedItemType;
  market_slug: string;
  market_title: string | null;
  platform: string | null;
  summary: string;
  confidence: number | null;
  target: string | null;
  timestamp: string; // ISO string
  payload: Record<string, unknown>;
}

export interface FeedPage {
  items: FeedItem[];
  limit: number;
  offset: number;
  total: number;
}

export interface FeedParams {
  limit?: number;
  offset?: number;
  item_type?: string; // comma-separated
  platform?: string;
}

export async function fetchFeed(params: FeedParams = {}): Promise<FeedPage> {
  if (!API_BASE) {
    return { items: [], limit: params.limit ?? 40, offset: params.offset ?? 0, total: 0 };
  }
  const qs = new URLSearchParams();
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.offset != null) qs.set("offset", String(params.offset));
  if (params.item_type) qs.set("item_type", params.item_type);
  if (params.platform) qs.set("platform", params.platform);

  try {
    const res = await fetch(`${API_BASE}/api/v1/feed?${qs.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) return { items: [], limit: params.limit ?? 40, offset: params.offset ?? 0, total: 0 };
    return (await res.json()) as FeedPage;
  } catch {
    return { items: [], limit: params.limit ?? 40, offset: params.offset ?? 0, total: 0 };
  }
}

/**
 * Open a WebSocket to /api/v1/ws/feed and call onItem for each "feed" channel message.
 * Returns a cleanup function.
 */
export function subscribeFeedWS(onItem: (item: FeedItem) => void): () => void {
  const wsUrl = WS_BASE
    ? `${WS_BASE}/api/v1/ws/feed`
    : `${typeof window !== "undefined" ? (window.location.protocol === "https:" ? "wss" : "ws") : "ws"}://${typeof window !== "undefined" ? window.location.host : "localhost"}/api/v1/ws/feed`;

  let ws: WebSocket | null = null;
  let dead = false;

  function connect() {
    if (dead) return;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as Record<string, unknown>;
          if (msg.channel === "feed") {
            onItem(msg as unknown as FeedItem);
          }
        } catch {
          // ignore parse errors
        }
      };
      ws.onerror = () => {
        ws?.close();
      };
      ws.onclose = () => {
        if (!dead) {
          setTimeout(connect, 5000);
        }
      };
    } catch {
      // WebSocket not available (SSR)
    }
  }

  connect();

  return () => {
    dead = true;
    ws?.close();
  };
}
