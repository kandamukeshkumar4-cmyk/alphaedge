import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";

import { closePaperPosition } from "./orders-api";

const __dirname = dirname(fileURLToPath(import.meta.url));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("closePaperPosition", () => {
  it("posts to /api/v1/positions/close with bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        order_id: "order-1",
        slug: "nba-2025-01-15-lal-bos",
        outcome: "yes",
        shares_sold: 10,
        proceeds: 6,
        realized_pnl: 2,
        remaining_shares: 0,
        remaining_balance: 100002,
        paper_trading_only: true,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const input = {
      slug: "nba-2025-01-15-lal-bos",
      outcome: "yes" as const,
      shares: 10,
      price: 0.6,
    };
    await closePaperPosition("test-token", input);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith("/api/v1/positions/close")).toBe(true);
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(init.body))).toEqual(input);
  });

  it("surfaces backend detail on error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Cannot sell more shares than held" }),
      }),
    );

    await expect(
      closePaperPosition("test-token", {
        slug: "nba-2025-01-15-lal-bos",
        outcome: "yes",
        shares: 5,
        price: 0.5,
      }),
    ).rejects.toThrow("Cannot sell more shares than held");
  });
});

describe("position card copy safety", () => {
  it("contains no banned execution copy", () => {
    const source = readFileSync(
      resolve(__dirname, "../components/PositionCard.tsx"),
      "utf8",
    ).toLowerCase();
    const banned = [
      "place bet",
      "auto bet",
      "guaranteed profit",
      "wallet",
      "private key",
      "real-money",
    ];
    for (const phrase of banned) {
      expect(source).not.toContain(phrase);
    }
  });
});
