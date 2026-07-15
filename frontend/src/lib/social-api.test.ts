import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchFollowing,
  fetchSocialFeed,
  fetchTraderProfile,
  followTrader,
  unfollowTrader,
} from "./social-api";

const profile = {
  username: "quant_kestrel",
  member_since: "2026-01-02T00:00:00Z",
  trade_count: 12,
  settled_trade_count: 9,
  win_rate: 0.66,
  roi: 0.12,
  followers_count: 4,
  following_count: 2,
  paper_trading_only: true,
};

describe("social API client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("loads a public profile with an encoded trader name", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => profile } as Response);

    await expect(
      fetchTraderProfile("display name", { apiBase: "http://api.test", fetcher }),
    ).resolves.toEqual(profile);
    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/social/traders/display%20name",
      { cache: "no-store" },
    );
  });

  it("uses the authenticated follow routes and returns the backend state", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          username: "quant_kestrel",
          following: true,
          changed: true,
          followers_count: 5,
          paper_trading_only: true,
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          username: "quant_kestrel",
          following: false,
          changed: true,
          followers_count: 4,
          paper_trading_only: true,
        }),
      } as Response);

    await followTrader("quant_kestrel", "jwt", { apiBase: "http://api.test", fetcher });
    await unfollowTrader("quant_kestrel", "jwt", { apiBase: "http://api.test", fetcher });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/social/follow/quant_kestrel",
      { method: "POST", cache: "no-store", headers: { Authorization: "Bearer jwt" } },
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/v1/social/follow/quant_kestrel",
      { method: "DELETE", cache: "no-store", headers: { Authorization: "Bearer jwt" } },
    );
  });

  it("keeps the social feed cursor and auth header in the request", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], next_cursor: null, limit: 20, paper_trading_only: true }),
    } as Response);

    await fetchSocialFeed("jwt", {
      apiBase: "http://api.test",
      cursor: "20",
      limit: 20,
      fetcher,
    });

    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/v1/social/feed?limit=20&cursor=20",
      { cache: "no-store", headers: { Authorization: "Bearer jwt" } },
    );
  });

  it("returns only public following labels", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ username: "quant_kestrel", member_since: profile.member_since }], total: 1, paper_trading_only: true }),
    } as Response);

    await expect(fetchFollowing("jwt", { apiBase: "http://api.test", fetcher })).resolves.toEqual([
      { username: "quant_kestrel", member_since: profile.member_since },
    ]);
  });
});
