import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop 98 (MU1–MU3) — Marketplace maturity DOM-assertion spec.
 * Client falls back to in-memory PAPER mocks when the live API is offline.
 * PAPER_TRADING_ONLY — no order path is touched.
 */
test.describe("Loop 98 marketplace maturity", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/skills cards expose mint star ratings", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/skills", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("skill-card").first()).toBeVisible({
      timeout: 20_000,
    });
    const rating = page.getByTestId("star-rating").first();
    await expect(rating).toBeVisible();
    await expect(rating).toHaveAttribute("data-kind", "skill");
    await expect(page.getByTestId("star-5").first()).toBeVisible();

    await page.getByTestId("star-4").first().click();
    await expect(page.getByTestId("star-rating-meta").first()).toContainText(/you 4|· 4|4/, {
      timeout: 10_000,
    });

    assertNoConsoleErrors(errors, "/skills rating");
  });

  test("/scanners cards expose star ratings", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("scanner-card").first()).toBeVisible({
      timeout: 20_000,
    });
    const rating = page.locator('[data-testid="scanner-card"] [data-testid="star-rating"]').first();
    await expect(rating).toBeVisible();
    await expect(rating).toHaveAttribute("data-kind", "scanner");

    assertNoConsoleErrors(errors, "/scanners rating");
  });

  test("/library shows Trending + Featured above tabs", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-hub")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("marketplace-spotlight")).toBeVisible({
      timeout: 20_000,
    });

    // Rows hydrate from mock catalogs (or show empty with reserved height).
    const trending = page.getByTestId("marketplace-trending-row");
    const trendingEmpty = page.getByTestId("marketplace-trending-empty");
    await expect(trending.or(trendingEmpty)).toBeVisible({ timeout: 20_000 });

    const featured = page.getByTestId("marketplace-featured-row");
    const featuredEmpty = page.getByTestId("marketplace-featured-empty");
    await expect(featured.or(featuredEmpty)).toBeVisible({ timeout: 20_000 });

    // Tabs still present below spotlight.
    await expect(page.getByTestId("library-tab-all")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Trending" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Featured" })).toBeVisible();

    if (await trending.isVisible()) {
      await expect(
        page.locator('[data-testid="marketplace-trending-row"] [data-testid="star-rating"]').first(),
      ).toBeVisible();
    }

    assertNoConsoleErrors(errors, "/library spotlight");
  });
});
