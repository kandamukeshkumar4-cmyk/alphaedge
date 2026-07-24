import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  getFeatured,
  getFeaturedSkills,
  getTrending,
  getTrendingSkills,
  rate,
  rateSkill,
  resetMarketplaceMockStore,
  setMarketplaceFetch,
} from "@/lib/marketplace-api";

/** Force the live-first client onto its mock fallback for every call. */
const offlineFetch: typeof fetch = () => Promise.reject(new Error("offline"));
const realFetch: typeof fetch = (...args) => fetch(...args);

describe("marketplace-api mock client", () => {
  beforeEach(() => {
    resetMarketplaceMockStore();
    setMarketplaceFetch(offlineFetch);
  });

  afterEach(() => {
    setMarketplaceFetch(realFetch);
  });

  it("rates a skill and returns avg / count / my_stars (mock)", async () => {
    const before = await rateSkill("confluence", 5);
    expect(before.source).toBe("mock");
    expect(before.rating.my_stars).toBe(5);
    expect(before.rating.count).toBe(6); // seeded 5 + first rate
    expect(before.rating.avg).toBeGreaterThan(0);

    // Re-rate updates my_stars without bumping count again.
    const again = await rate("skill", "confluence", 4);
    expect(again.rating.my_stars).toBe(4);
    expect(again.rating.count).toBe(6);
  });

  it("returns trending items sorted by trending_score desc", async () => {
    const { items, source } = await getTrendingSkills(10);
    expect(source).toBe("mock");
    expect(items.length).toBeGreaterThan(0);
    for (let i = 1; i < items.length; i += 1) {
      expect(items[i - 1].trending_score).toBeGreaterThanOrEqual(
        items[i].trending_score,
      );
    }
    expect(items[0]).toEqual(
      expect.objectContaining({
        kind: "skill",
        avg_rating: expect.any(Number),
        rating_count: expect.any(Number),
        trending_score: expect.any(Number),
      }),
    );

    const scanners = await getTrending("scanner", 5);
    expect(scanners.source).toBe("mock");
    expect(scanners.items.every((i) => i.kind === "scanner")).toBe(true);
  });

  it("returns featured items from the mock catalog", async () => {
    const { items, source } = await getFeaturedSkills();
    expect(source).toBe("mock");
    expect(items.length).toBeGreaterThan(0);
    expect(items.every((i) => i.is_featured && i.kind === "skill")).toBe(true);
    expect(items.map((i) => i.id)).toEqual(
      expect.arrayContaining(["confluence", "whale"]),
    );

    const scanners = await getFeatured("scanner");
    expect(scanners.items.every((i) => i.kind === "scanner" && i.is_featured)).toBe(
      true,
    );
    expect(scanners.items.some((i) => i.id === "scn-mock-whale")).toBe(true);
  });
});
