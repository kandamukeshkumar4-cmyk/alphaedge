import { test, expect } from "@playwright/test";
import { localApiBase } from "./helpers/local-api";

/**
 * Q3 (loop54) — API contract for GET /api/v1/system/resolved-count.
 * Uses Playwright request (same pattern as helpers/local-api.ts) against the
 * local stack — asserts V51 population shape without touching app source.
 */

test.describe("Q3 resolved-count API contract", () => {
  test("GET /api/v1/system/resolved-count exposes cluster + population.verdict", async ({
    request,
  }) => {
    const res = await request.get(
      `${localApiBase()}/api/v1/system/resolved-count`,
    );
    expect(res.ok(), `resolved-count HTTP ${res.status()}`).toBe(true);

    const body = (await res.json()) as Record<string, unknown>;

    // Top-level cluster disclosure (V51)
    expect(body).toHaveProperty("correlation_clusters");
    expect(typeof body.correlation_clusters).toBe("number");
    expect(Number.isFinite(body.correlation_clusters as number)).toBe(true);
    expect(body.correlation_clusters as number).toBeGreaterThanOrEqual(0);

    // Nested population carries the A/B cluster threshold + composition verdict
    expect(body).toHaveProperty("population");
    expect(body.population).not.toBeNull();
    expect(typeof body.population).toBe("object");

    const population = body.population as Record<string, unknown>;

    expect(population).toHaveProperty("ab_cluster_threshold");
    expect(typeof population.ab_cluster_threshold).toBe("number");
    expect(Number.isFinite(population.ab_cluster_threshold as number)).toBe(
      true,
    );
    expect(population.ab_cluster_threshold as number).toBeGreaterThan(0);

    expect(population).toHaveProperty("verdict");
    expect(typeof population.verdict).toBe("string");
    expect((population.verdict as string).length).toBeGreaterThan(0);

    // Sanity: population also names its own cluster count (same family as top-level)
    expect(population).toHaveProperty("correlation_clusters");
    expect(typeof population.correlation_clusters).toBe("number");
  });
});
