import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchSignalEvents } from "./activity-api";

describe("fetchSignalEvents", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("requests the backend dedupe window for the Live Signals rail", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await fetchSignalEvents({ limit: 30, dedupeWindowMinutes: 10 });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/v1/signals/events?limit=30&dedupe_window_minutes=10",
      { cache: "no-store" },
    );
  });
});
