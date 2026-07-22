import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V83 (S1–S4) — Skills gallery DOM-assertion spec.
 * The skills client falls back to an in-memory mock catalog when the live API
 * is offline, so the gallery renders cards without the backend. Run click
 * POSTs run and navigates to /terminal?session={id}.
 */
test.describe("V83 skills gallery", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/skills renders skill cards from the mock catalog", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/skills", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("skills-gallery")).toBeVisible({ timeout: 30_000 });
    const cards = page.getByTestId("skill-card");
    await expect(cards.first()).toBeVisible({ timeout: 20_000 });
    await expect(cards).toHaveCount(await cards.count());

    // Each card exposes a Run button.
    await expect(page.getByTestId("skill-run").first()).toBeVisible();

    await page.waitForTimeout(500);
    assertNoConsoleErrors(errors, "/skills");
  });

  test("Run navigates to a terminal session", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/skills", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("skill-card").first()).toBeVisible({
      timeout: 20_000,
    });

    await page.getByTestId("skill-run").first().click();

    await expect(page).toHaveURL(/\/terminal/, { timeout: 30_000 });
    await expect(page).toHaveURL(/session=/, { timeout: 30_000 });
    await expect(page.getByTestId("terminal-page")).toBeVisible({ timeout: 30_000 });

    assertNoConsoleErrors(errors, "/skills run");
  });
});
