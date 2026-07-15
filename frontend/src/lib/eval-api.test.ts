import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchDriftSeries, fetchModelRegistry } from "./eval-api";

describe("eval API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads the public persisted drift series without credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ series: [], count: 0, latest_degraded: false, paper_trading_only: true }),
    } as Response);
    vi.stubGlobal("fetch", fetcher);

    await expect(fetchDriftSeries()).resolves.toMatchObject({ count: 0, paper_trading_only: true });
    expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/api\/v1\/eval\/drift$/), { cache: "no-store" });
  });

  it("lists model versions with the admin key and never calls without one", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ models: [], active_model_id: null, count: 0 }),
    } as Response);
    vi.stubGlobal("fetch", fetcher);

    await expect(fetchModelRegistry(" ")).resolves.toBeNull();
    expect(fetcher).not.toHaveBeenCalled();

    await expect(fetchModelRegistry("admin-secret")).resolves.toMatchObject({ count: 0 });
    expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/api\/v1\/models$/), {
      cache: "no-store",
      headers: { "X-Admin-API-Key": "admin-secret" },
    });
  });
});
