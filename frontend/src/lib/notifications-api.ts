import { API_BASE, apiUrl, ensureApiBase, hasLiveApi, WS_BASE } from "./alphaedge-api";

export type NotificationItem = {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  created_at: string | null;
  unread: boolean;
};

export type NotificationPage = {
  items: NotificationItem[];
  next_cursor: string | null;
  limit: number;
  unread_count: number;
  paper_trading_only: boolean;
  disclaimer?: string;
};

export type NotificationReadResponse = {
  id: string;
  read_at: string | null;
  paper_trading_only: boolean;
};

export type NotificationReadAllResponse = {
  marked: number;
  paper_trading_only: boolean;
};

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

function fetcher(input?: Fetcher): Fetcher {
  return input ?? fetch;
}

async function baseUrl(): Promise<string> {
  return (await ensureApiBase()) || API_BASE;
}

function bearer(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function emptyPage(limit: number): NotificationPage {
  return {
    items: [],
    next_cursor: null,
    limit,
    unread_count: 0,
    paper_trading_only: true,
  };
}

export async function fetchNotifications(
  token: string,
  input?: {
    apiBase?: string;
    cursor?: string | null;
    limit?: number;
    unreadOnly?: boolean;
    fetcher?: Fetcher;
  },
): Promise<NotificationPage> {
  const limit = input?.limit ?? 50;
  const base = input?.apiBase ?? (await baseUrl());
  if (!token || !hasLiveApi(base)) return emptyPage(limit);

  const query = new URLSearchParams({ limit: String(limit) });
  if (input?.cursor) query.set("cursor", input.cursor);
  if (input?.unreadOnly) query.set("unread_only", "true");
  try {
    const response = await fetcher(input?.fetcher)(
      `${apiUrl("/api/v1/notifications", base)}?${query.toString()}`,
      { cache: "no-store", headers: bearer(token) },
    );
    if (!response.ok) return emptyPage(limit);
    return (await response.json()) as NotificationPage;
  } catch {
    return emptyPage(limit);
  }
}

export async function markNotificationRead(
  token: string,
  id: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<NotificationReadResponse | null> {
  const base = input?.apiBase ?? (await baseUrl());
  if (!token || !hasLiveApi(base)) return null;
  try {
    const response = await fetcher(input?.fetcher)(
      apiUrl(`/api/v1/notifications/${encodeURIComponent(id)}/read`, base),
      { method: "POST", cache: "no-store", headers: bearer(token) },
    );
    if (!response.ok) return null;
    return (await response.json()) as NotificationReadResponse;
  } catch {
    return null;
  }
}

export async function markAllNotificationsRead(
  token: string,
  input?: { apiBase?: string; fetcher?: Fetcher },
): Promise<NotificationReadAllResponse | null> {
  const base = input?.apiBase ?? (await baseUrl());
  if (!token || !hasLiveApi(base)) return null;
  try {
    const response = await fetcher(input?.fetcher)(
      apiUrl("/api/v1/notifications/read-all", base),
      { method: "POST", cache: "no-store", headers: bearer(token) },
    );
    if (!response.ok) return null;
    return (await response.json()) as NotificationReadAllResponse;
  } catch {
    return null;
  }
}

export type NotificationSocketPayload = {
  id: string;
  user_id?: string;
  notification_type?: string;
  title: string;
  body: string;
  link?: string | null;
  created_at?: string | null;
};

function toNotification(payload: NotificationSocketPayload): NotificationItem {
  return {
    id: payload.id,
    type: payload.notification_type ?? "info",
    title: payload.title,
    body: payload.body,
    link: payload.link ?? null,
    read_at: null,
    created_at: payload.created_at ?? new Date().toISOString(),
    unread: true,
  };
}

/** Subscribe to the existing multiplexed feed socket's per-user notification channel. */
export function subscribeNotificationsWS(
  onNotification: (item: NotificationItem) => void,
  userId?: string | null,
): () => void {
  if (typeof window === "undefined") return () => undefined;
  const sameOrigin = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
  const wsUrl = `${WS_BASE || sameOrigin}/api/v1/ws/feed`;
  let socket: WebSocket | null = null;
  let stopped = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (stopped) return;
    try {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data as string) as {
            channel?: string;
            type?: string;
            user_id?: string;
            id?: string;
            title?: string;
            body?: string;
            notification_type?: string;
            link?: string | null;
            created_at?: string | null;
          };
          if (
            message.channel !== "notifications" ||
            message.type !== "notification" ||
            !message.id ||
            !message.title ||
            !message.body
          ) {
            return;
          }
          // The backend frame carries the owning user id. Filter it when the
          // JWT exposes a subject; accepting the frame when no subject is
          // available keeps compatibility with opaque auth tokens.
          if (userId && message.user_id && message.user_id !== userId) return;
          onNotification(
            toNotification({
              id: message.id,
              user_id: message.user_id,
              notification_type: message.notification_type,
              title: message.title,
              body: message.body,
              link: message.link,
              created_at: message.created_at,
            }),
          );
        } catch {
          // Ignore malformed frames and keep the notification center alive.
        }
      };
      socket.onclose = () => {
        if (!stopped) reconnectTimer = setTimeout(connect, 5000);
      };
      socket.onerror = () => socket?.close();
    } catch {
      if (!stopped) reconnectTimer = setTimeout(connect, 5000);
    }
  }

  connect();
  return () => {
    stopped = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    socket?.close();
  };
}
