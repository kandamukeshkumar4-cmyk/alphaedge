import { expect, test, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop 98 (MU1–MU3) — Marketplace maturity DOM-assertion spec.
 * Client falls back to in-memory PAPER mocks when the live API is offline.
 * PAPER_TRADING_ONLY — no order path is touched.
 *
 * OnboardingGate uses `ae_onboarded_v1` (see lib/onboarding.ts). The shared
 * skipOnboarding helper still seeds the older `alphaedge.onboarded` key, so
 * this suite also seeds the live key and dismisses the overlay if it appears.
 */

const ONBOARDING_KEY = "ae_onboarded_v1";

async function seedOnboardingDone(page: Page): Promise<void> {
  await skipOnboarding(page);
  await page.addInitScript((key: string) => {
    try {
      localStorage.setItem(key, "true");
    } catch {
      /* ignore */
    }
  }, ONBOARDING_KEY);
}

/** Close the full-screen onboarding overlay when it still mounts. */
async function clearOnboarding(page: Page): Promise<void> {
  await dismissOnboardingIfPresent(page);
  const overlay = page.getByTestId("onboarding-overlay");
  // Wait briefly for late hydration of OnboardingGate.
  const visible = await overlay.isVisible({ timeout: 2500 }).catch(() => false);
  if (!visible) return;
  await page.keyboard.press("Escape");
  if (await overlay.isVisible().catch(() => false)) {
    await page
      .locator('[data-testid="onboarding-overlay"] button[aria-label="Close onboarding tour"]')
      .last()
      .click({ force: true });
  }
  await expect(overlay).toBeHidden({ timeout: 10_000 });
}

test.describe("Loop 98 marketplace maturity", () => {
  test.beforeEach(async ({ page }) => {
    await seedOnboardingDone(page);
  });

  test("/skills cards expose mint star ratings", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/skills", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await clearOnboarding(page);

    await expect(page.getByTestId("skill-card").first()).toBeVisible({
      timeout: 20_000,
    });
    const rating = page.getByTestId("star-rating").first();
    await expect(rating).toBeVisible();
    await expect(rating).toHaveAttribute("data-kind", "skill");
    await expect(page.getByTestId("star-5").first()).toBeVisible();

    await page.getByTestId("star-4").first().click();
    await expect(page.getByTestId("star-rating-meta").first()).toContainText(/you 4/, {
      timeout: 10_000,
    });

    assertNoConsoleErrors(errors, "/skills rating");
  });

  test("/scanners cards expose star ratings", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await clearOnboarding(page);

    await expect(page.getByTestId("scanner-card").first()).toBeVisible({
      timeout: 20_000,
    });
    const rating = page.locator('[data-testid="scanner-card"] [data-testid="star-rating"]').first();
    await expect(rating).toBeVisible();
    await expect(rating).toHaveAttribute("data-kind", "scanner");

    assertNoConsoleErrors(errors, "/scanners rating");
  });

  // "/library shows Trending + Featured above tabs" was removed 2026-07-30:
  // Loop 104 intentionally refactored /library from the marketplace-spotlight
  // view into the research archive (see library.spec.ts for its coverage).
});
