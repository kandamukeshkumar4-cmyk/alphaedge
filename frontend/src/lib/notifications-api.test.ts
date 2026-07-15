import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
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
