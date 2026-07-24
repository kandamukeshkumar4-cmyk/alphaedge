import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchNotifications,
  getPrefs,
  list,
  markAll,
  markAllNotificationsRead,
  markNotificationRead,
  markRead,
  putPrefs,
  resetV90MockStore,
} from "./notifications-api";

describe("notifications API client", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("loads a cursor page with the auth header", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], next_cursor: "50", limit: 50, unread_count: 2, paper_trading_only: true }),
    } as Response);

    await fetchNotifications("jwt", { apiBase: "http://api.test", cursor: "0", fetcher });

    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/notifications?limit=50&cursor=0",
      { cache: "no-store", headers: { Authorization: "Bearer jwt" } },
    );
  });

  it("marks one notification read and supports mark-all", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "n1", read_at: "now", paper_trading_only: true }) } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ marked: 2, paper_trading_only: true }) } as Response);

    await markNotificationRead("jwt", "n1", { apiBase: "http://api.test", fetcher });
    await markAllNotificationsRead("jwt", { apiBase: "http://api.test", fetcher });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/notifications/n1/read",
      { method: "POST", cache: "no-store", headers: { Authorization: "Bearer jwt" } },
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/v1/notifications/read-all",
      { method: "POST", cache: "no-store", headers: { Authorization: "Bearer jwt" } },
    );
  });
});

// Loop V90 (C1) — frozen contract client: live-first + mandatory mock fallback.
describe("notifications V90 client (loop90 frozen contract)", () => {
  beforeEach(() => resetV90MockStore());

  it("list() hits GET /api/v1/notifications?limit=30 with the bearer token and returns live items", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            id: "n1",
            type: "whale",
            title: "Whale flow",
            body: "Large YES buy",
            read: false,
            created_at: "2026-07-23T10:00:00.000Z",
            link: "/markets/nba-2025-01-15-lal-bos",
          },
        ],
        unread: 1,
      }),
    } as Response);

    const result = await list("jwt", { apiBase: "http://api.test", fetcher });

    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/notifications?limit=30",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer jwt" }) }),
    );
    expect(result.source).toBe("live");
    expect(result.unread).toBe(1);
    expect(result.items).toEqual([
      {
        id: "n1",
        type: "whale",
        title: "Whale flow",
        body: "Large YES buy",
        read: false,
        created_at: "2026-07-23T10:00:00.000Z",
        link: "/markets/nba-2025-01-15-lal-bos",
      },
    ]);
  });

  it("list() falls back to the seeded PAPER mock when the live API fails", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("backend down"));

    const result = await list(null, { apiBase: "http://api.test", fetcher });

    expect(result.source).toBe("mock");
    expect(result.items.length).toBeGreaterThan(0);
    expect(result.unread).toBe(result.items.filter((item) => !item.read).length);
    expect(result.items[0]).toMatchObject({ id: expect.any(String), title: expect.any(String) });
  });

  it("markRead() and markAll() POST the contract routes", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "v90-n1" }) } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ marked: 3 }) } as Response);

    const one = await markRead("v90-n1", "jwt", { apiBase: "http://api.test", fetcher });
    const all = await markAll("jwt", { apiBase: "http://api.test", fetcher });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/notifications/v90-n1/read",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/v1/notifications/read-all",
      expect.objectContaining({ method: "POST" }),
    );
    expect(one).toEqual({ ok: true, source: "live" });
    expect(all).toEqual({ ok: true, marked: 3, source: "live" });
  });

  it("getPrefs()/putPrefs() round-trip GET|PUT /api/v1/notifications/preferences, mock on failure", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ email_digest: false, in_app: true, fired_alerts: false }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ email_digest: true, in_app: true, fired_alerts: true }),
      } as Response);

    const got = await getPrefs("jwt", { apiBase: "http://api.test", fetcher });
    const put = await putPrefs(
      { email_digest: true, in_app: true, fired_alerts: true },
      "jwt",
      { apiBase: "http://api.test", fetcher },
    );

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/notifications/preferences",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer jwt" }) }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/v1/notifications/preferences",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ email_digest: true, in_app: true, fired_alerts: true }),
      }),
    );
    expect(got).toEqual({
      prefs: { email_digest: false, in_app: true, fired_alerts: false },
      source: "live",
    });
    expect(put.ok).toBe(true);
    expect(put.source).toBe("live");

    // Failure → mock fallback keeps the UI responsive (store applies the change).
    const failing = vi.fn().mockRejectedValue(new Error("offline"));
    const mockPut = await putPrefs(
      { email_digest: false, in_app: false, fired_alerts: false },
      null,
      { apiBase: "http://api.test", fetcher: failing },
    );
    expect(mockPut).toEqual({
      ok: true,
      prefs: { email_digest: false, in_app: false, fired_alerts: false },
      source: "mock",
    });
    const mockGot = await getPrefs(null, { apiBase: "http://api.test", fetcher: failing });
    expect(mockGot).toEqual({
      prefs: { email_digest: false, in_app: false, fired_alerts: false },
      source: "mock",
    });
  });
});
