import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V85 (L1–L4) — Library + Screener DOM-assertion spec.
 *
 * Both surfaces fall back to in-memory PAPER mocks when the live API is
 * offline (screener-api / community-api / skills-api / scanners-api), so the
 * page renders without the backend. The local stack boots next dev + uvicorn;
 * the mock path is what these assertions exercise.
 *
 * PAPER_TRADING_ONLY — no order path is touched by any action here.
 */
test.describe("V85 library + screener", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/screener renders the dense table from the mock feed", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/screener", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("screener-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("screener-filters")).toBeVisible();

    // Rows render from the mock catalog.
    const rows = page.getByTestId("screener-row");
    await expect(rows.first()).toBeVisible({ timeout: 20_000 });
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // Edge column is present on every row.
    await expect(page.getByTestId("screener-edge").first()).toBeVisible();

    await page.waitForTimeout(400);
    assertNoConsoleErrors(errors, "/screener");
  });

  test("/library tabs switch between Skills / Scanners / Subscribed", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-hub")).toBeVisible({ timeout: 30_000 });
    // Wait for cards to hydrate from the mock catalogs.
    await expect(page.getByTestId("library-card").first()).toBeVisible({
      timeout: 20_000,
    });

    // Scanners tab exposes only scanner cards.
    await page.getByTestId("library-tab-scanners").click();
    await expect(page.getByTestId("library-card").first()).toBeVisible();
    const scannerCount = await page.locator('[data-testid="library-card"][data-kind="scanner"]').count();
    const skillCount = await page.locator('[data-testid="library-card"][data-kind="skill"]').count();
    expect(scannerCount).toBeGreaterThan(0);
    expect(skillCount).toBe(0);

    // Skills tab exposes only skill cards.
    await page.getByTestId("library-tab-skills").click();
    await expect(
      page.locator('[data-testid="library-card"][data-kind="skill"]').first(),
    ).toBeVisible();
    expect(
      await page.locator('[data-testid="library-card"][data-kind="scanner"]').count(),
    ).toBe(0);

    // Subscribed tab is populated from the subscriptions mock.
    await page.getByTestId("library-tab-subscribed").click();
    await expect(page.getByTestId("library-card").first()).toBeVisible();

    assertNoConsoleErrors(errors, "/library tabs");
  });

  test("Fork shows a branded toast confirmation", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-card").first()).toBeVisible({
      timeout: 20_000,
    });

    await page.getByTestId("library-fork").first().click();

    // Branded success toast (role=status, polite) with the Forked title.
    await expect(
      page.getByRole("status").filter({ hasText: "Forked" }),
    ).toBeVisible({ timeout: 10_000 });

    assertNoConsoleErrors(errors, "/library fork");
  });
});
