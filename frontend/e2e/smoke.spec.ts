import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";

/**
 * Q1 — smoke against local uvicorn + next dev stack.
 * / renders, zero app console errors, markets grid non-empty.
 */
test.describe("Q1 smoke", () => {
  test("/ renders with non-empty markets grid and zero console errors", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });

    await expect(page.locator("body")).toBeVisible();
    // Markets grid: discover shell links into /markets/<slug>
    const cards = page.locator('a[href^="/markets/"]');
    await expect(cards.first()).toBeVisible({ timeout: 30_000 });
    expect(await cards.count()).toBeGreaterThan(0);

    // Allow client fetch/hydration to settle before judging console.
    await page.waitForTimeout(1500);
    assertNoConsoleErrors(errors, "/");
  });
});
