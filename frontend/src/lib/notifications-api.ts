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

// ---------------------------------------------------------------------------
// Loop V90 (C1) — FROZEN notifications contract client (node E-A backend).
//
//   GET  /api/v1/notifications?limit=30
//        -> {"items":[{id,type,title,body,read,created_at,link}],"unread":N}
//   POST /api/v1/notifications/{id}/read
//   POST /api/v1/notifications/read-all
//   GET|PUT /api/v1/notifications/preferences
//        -> {email_digest,in_app,fired_alerts}
//
// Live-first with a MANDATORY in-memory PAPER mock fallback (same pattern as
// terminal-api.ts): node E-A lands in parallel, so the UI must be verifiable
// with no backend at all. Nothing here ever rejects — every function resolves
// to a typed result tagged with its source. Prefs are a STORED preference
// only: paper-trading simulation, no external delivery of any kind.
// ---------------------------------------------------------------------------

export type NotificationV90 = {
  id: string;
  type: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  link: string | null;
};

export type NotificationPrefsV90 = {
  email_digest: boolean;
  in_app: boolean;
  fired_alerts: boolean;
};

export type NotificationsV90Source = "live" | "mock";

export type NotificationListV90 = {
  items: NotificationV90[];
  unread: number;
  source: NotificationsV90Source;
};

export type NotificationMarkV90 = {
  ok: boolean;
  source: NotificationsV90Source;
};

export type NotificationMarkAllV90 = {
  ok: boolean;
  marked: number;
  source: NotificationsV90Source;
};

export type NotificationPrefsResultV90 = {
  prefs: NotificationPrefsV90;
  source: NotificationsV90Source;
};

export type NotificationPutPrefsResultV90 = {
  ok: boolean;
  prefs: NotificationPrefsV90;
  source: NotificationsV90Source;
};

type V90Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

type V90CallOptions = {
  apiBase?: string;
  fetcher?: V90Fetcher;
};

const V90_DEFAULT_PREFS: NotificationPrefsV90 = {
  email_digest: false,
  in_app: true,
  fired_alerts: true,
};

function asV90Record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

/** Tolerant item normalizer — the backend sends dicts; never throw on drift. */
export function normalizeNotificationV90(raw: unknown): NotificationV90 | null {
  const rec = asV90Record(raw);
  if (typeof rec.id !== "string" || rec.id === "") return null;
  const read =
    typeof rec.read === "boolean"
      ? rec.read
      : typeof rec.read_at === "string" && rec.read_at !== "";
  return {
    id: rec.id,
    type: typeof rec.type === "string" && rec.type !== "" ? rec.type : "info",
    title: typeof rec.title === "string" ? rec.title : "Notification",
    body: typeof rec.body === "string" ? rec.body : "",
    read,
    created_at:
      typeof rec.created_at === "string" && rec.created_at !== ""
        ? rec.created_at
        : new Date(0).toISOString(),
    link: typeof rec.link === "string" && rec.link !== "" ? rec.link : null,
  };
}

function normalizePrefsV90(raw: unknown): NotificationPrefsV90 {
  const rec = asV90Record(raw);
  return {
    email_digest:
      typeof rec.email_digest === "boolean" ? rec.email_digest : V90_DEFAULT_PREFS.email_digest,
    in_app: typeof rec.in_app === "boolean" ? rec.in_app : V90_DEFAULT_PREFS.in_app,
    fired_alerts:
      typeof rec.fired_alerts === "boolean" ? rec.fired_alerts : V90_DEFAULT_PREFS.fired_alerts,
  };
}

// ---- Mock store (in-memory; used whenever the live API is absent/failing) --

/** Build the seeded PAPER notifications with fresh relative timestamps. */
function seedV90Store(): NotificationV90[] {
  const at = (minutesAgo: number) => new Date(Date.now() - minutesAgo * 60_000).toISOString();
  return [
    {
      id: "v90-n1",
      type: "whale",
      title: "Whale flow — Lakers YES",
      body: "Two large YES buys (20.5K sim units) detected on nba-2025-01-15-lal-bos.",
      read: false,
      created_at: at(12),
      link: "/markets/nba-2025-01-15-lal-bos",
    },
    {
      id: "v90-n2",
      type: "model",
      title: "Model edge crossed +4 pts",
      body: "Ensemble P(YES) 0.56 vs market mid 0.52 — paper edge above research threshold.",
      read: false,
      created_at: at(47),
      link: "/terminal",
    },
    {
      id: "v90-n3",
      type: "news",
      title: "News alert — injury watch",
      body: "Lakers carry a questionable tag; no late scratch as of the last wire update.",
      read: false,
      created_at: at(128),
      link: "/markets/nba-2025-01-15-lal-bos",
    },
    {
      id: "v90-n4",
      type: "resolution",
      title: "Paper position resolved",
      body: "Your simulated Celtics moneyline position settled. PAPER ONLY — no funds moved.",
      read: true,
      created_at: at(26 * 60),
      link: "/portfolio",
    },
  ];
}

let v90MockItems: NotificationV90[] = seedV90Store();
let v90MockPrefs: NotificationPrefsV90 = { email_digest: true, in_app: true, fired_alerts: true };

/** Reset the PAPER mock store to its seeded state (tests / offline demos). */
export function resetV90MockStore(): void {
  v90MockItems = seedV90Store();
  v90MockPrefs = { email_digest: true, in_app: true, fired_alerts: true };
}

async function v90Base(input?: V90CallOptions): Promise<string> {
  return input?.apiBase ?? ((await ensureApiBase()) || API_BASE);
}

async function tryV90Live(
  path: string,
  token: string | null,
  init: RequestInit | undefined,
  input: V90CallOptions | undefined,
): Promise<Response | null> {
  const base = await v90Base(input);
  if (!hasLiveApi(base)) return null;
  try {
    const response = await (input?.fetcher ?? fetch)(apiUrl(path, base), {
      cache: "no-store",
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    });
    return response;
  } catch {
    return null;
  }
}

async function readJsonTolerant(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function v90UnreadCount(items: NotificationV90[]): number {
  return items.reduce((count, item) => (item.read ? count : count + 1), 0);
}

/**
 * List notifications (contract: GET /api/v1/notifications?limit=30).
 * Live-first; falls back to the seeded PAPER mock only when the live API is
 * absent, errors, or returns a malformed page. A valid empty live page is an
 * honest empty, never replaced with mock items. Never rejects.
 */
export async function list(
  token: string | null = null,
  input?: V90CallOptions & { limit?: number },
): Promise<NotificationListV90> {
  const limit = input?.limit ?? 30;
  const response = await tryV90Live(
    `/api/v1/notifications?limit=${limit}`,
    token,
    undefined,
    input,
  );
  if (response && response.ok) {
    const rec = asV90Record(await readJsonTolerant(response));
    // A valid live page — including an EMPTY one — is authoritative. Swapping
    // an honest "no notifications" for seeded mock items would fabricate data;
    // the mock fallback is only for an absent/error/malformed live API.
    if (Array.isArray(rec.items)) {
      const items = rec.items
        .map(normalizeNotificationV90)
        .filter((item): item is NotificationV90 => item !== null);
      const unread = typeof rec.unread === "number" ? rec.unread : v90UnreadCount(items);
      return { items, unread, source: "live" };
    }
  }
  return { items: [...v90MockItems], unread: v90UnreadCount(v90MockItems), source: "mock" };
}

/**
 * Mark one notification read (contract: POST /api/v1/notifications/{id}/read).
 * Live-first; on any failure falls back to marking the PAPER mock store so the
 * UI flow completes offline. Never rejects.
 */
export async function markRead(
  id: string,
  token: string | null = null,
  input?: V90CallOptions,
): Promise<NotificationMarkV90> {
  const response = await tryV90Live(
    `/api/v1/notifications/${encodeURIComponent(id)}/read`,
    token,
    { method: "POST" },
    input,
  );
  if (response && response.ok) {
    v90MockItems = v90MockItems.map((item) => (item.id === id ? { ...item, read: true } : item));
    return { ok: true, source: "live" };
  }
  const target = v90MockItems.find((item) => item.id === id);
  if (!target) return { ok: false, source: "mock" };
  v90MockItems = v90MockItems.map((item) => (item.id === id ? { ...item, read: true } : item));
  return { ok: true, source: "mock" };
}

/**
 * Mark every notification read (contract: POST /api/v1/notifications/read-all).
 * Live-first with the same mock fallback. `marked` is the backend count when
 * live reports one, else the mock unread count. Never rejects.
 */
export async function markAll(
  token: string | null = null,
  input?: V90CallOptions,
): Promise<NotificationMarkAllV90> {
  const response = await tryV90Live("/api/v1/notifications/read-all", token, { method: "POST" }, input);
  if (response && response.ok) {
    const rec = asV90Record(await readJsonTolerant(response));
    const marked = typeof rec.marked === "number" ? rec.marked : v90UnreadCount(v90MockItems);
    v90MockItems = v90MockItems.map((item) => ({ ...item, read: true }));
    return { ok: true, marked, source: "live" };
  }
  const marked = v90UnreadCount(v90MockItems);
  v90MockItems = v90MockItems.map((item) => ({ ...item, read: true }));
  return { ok: true, marked, source: "mock" };
}

/**
 * Read notification preferences (contract: GET /api/v1/notifications/preferences
 * -> {email_digest,in_app,fired_alerts}). Live-first; falls back to the PAPER
 * mock prefs store. Never rejects.
 */
export async function getPrefs(
  token: string | null = null,
  input?: V90CallOptions,
): Promise<NotificationPrefsResultV90> {
  const response = await tryV90Live("/api/v1/notifications/preferences", token, undefined, input);
  if (response && response.ok) {
    const prefs = normalizePrefsV90(await readJsonTolerant(response));
    v90MockPrefs = prefs;
    return { prefs, source: "live" };
  }
  return { prefs: { ...v90MockPrefs }, source: "mock" };
}

/**
 * Store notification preferences (contract: PUT /api/v1/notifications/preferences).
 * The ONLY mutation on this path — a stored preference, never an order, and
 * never any external delivery (paper-trading simulation). Live-first; on
 * failure the change is applied to the mock store so the UI still responds.
 * Never rejects.
 */
export async function putPrefs(
  prefs: NotificationPrefsV90,
  token: string | null = null,
  input?: V90CallOptions,
): Promise<NotificationPutPrefsResultV90> {
  const response = await tryV90Live(
    "/api/v1/notifications/preferences",
    token,
    { method: "PUT", body: JSON.stringify(prefs) },
    input,
  );
  if (response && response.ok) {
    const echoed = await readJsonTolerant(response);
    const normalized = normalizePrefsV90(echoed ?? prefs);
    v90MockPrefs = normalized;
    return { ok: true, prefs: normalized, source: "live" };
  }
  v90MockPrefs = { ...prefs };
  return { ok: true, prefs: { ...prefs }, source: "mock" };
}
