import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V84 U4 — Scanner Studio smoke.
 * The scanners client falls back to its in-memory PAPER mock when the live
 * API is absent/empty, so the list, the compile preview and the detail
 * canvas all render without the backend.
 */
test.describe("V84 Scanner Studio", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/scanners renders the list from mock and a compile preview appears", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("scanners-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Scanners", exact: true })).toBeVisible();
    await expect(page.getByTestId("scanners-paper-banner")).toBeVisible();

    // Mock store seeds three scanners (active / paused / draft).
    const cards = page.getByTestId("scanner-card");
    await expect(cards.first()).toBeVisible({ timeout: 20_000 });
    expect(await cards.count()).toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("scanner-status-pill").first()).toBeVisible();

    // Composer flow: describe → compile → spec preview with step chips.
    await page
      .getByTestId("scanners-request-input")
      .fill("Scan NBA markets with whale flow and price trend every 15 minutes, volume above 50,000");
    await page.getByTestId("scanners-compile").click();
    await expect(page.getByTestId("scanners-preview")).toBeVisible({ timeout: 20_000 });
    const chips = page.getByTestId("scanners-preview-steps").locator("li");
    await expect(chips.first()).toBeVisible();
    expect(await chips.count()).toBeGreaterThanOrEqual(2);

    assertNoConsoleErrors(errors, "/scanners");
  });

  test("scanner detail renders the pipeline canvas with >=3 nodes", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanner-card").first()).toBeVisible({ timeout: 20_000 });

    // Seeded mock scanner with a 5-step spec (unknown id live → mock fallback).
    await page.goto("/scanners/scn-mock-whale", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByTestId("scanner-detail-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("scanner-detail-paper-banner")).toBeVisible();
    await expect(page.getByTestId("scanner-canvas")).toBeVisible({ timeout: 20_000 });

    const nodes = page.locator(".react-flow__node");
    await expect(async () => {
      expect(await nodes.count()).toBeGreaterThanOrEqual(3);
    }).toPass({ timeout: 15_000 });
    await expect(page.getByTestId("scanner-step-node").first()).toBeVisible();

    // Latest run panel + runs history render.
    await expect(page.getByTestId("scanner-latest-run")).toBeVisible();
    await expect(page.getByTestId("scanner-candidates")).toBeVisible();
    await expect(page.getByTestId("scanner-runs-history")).toBeVisible();

    assertNoConsoleErrors(errors, "/scanners/[id]");
  });
});
