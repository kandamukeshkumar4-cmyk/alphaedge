import { expect, test } from "@playwright/test";

const ONBOARDING_KEY = "ae_onboarded_v1";

test.describe("first-run onboarding", () => {
  test("shows the tour and Skip persists completion", async ({ page, context }) => {
    await context.clearCookies();

    // Land on origin, then clear any prior onboarded flag so isFirstRun() is true.
    await page.goto("/");
    await page.evaluate((key) => {
      window.localStorage.removeItem(key);
    }, ONBOARDING_KEY);
    await page.reload();

    const overlay = page.getByTestId("onboarding-overlay");
    await expect(overlay).toBeVisible();
    await expect(overlay).toContainText(
      "AlphaEdge — AI research desk for paper prediction-market trading. Simulated funds only.",
    );

    await overlay.getByRole("button", { name: "Skip" }).click();
    await expect(overlay).toBeHidden();
    await expect
      .poll(() => page.evaluate((key) => window.localStorage.getItem(key), ONBOARDING_KEY))
      .toBe("true");

    // Reload must keep the flag and must not show the overlay again.
    await page.reload();
    await expect(page.getByTestId("onboarding-overlay")).toHaveCount(0);
    await expect
      .poll(() => page.evaluate((key) => window.localStorage.getItem(key), ONBOARDING_KEY))
      .toBe("true");
  });
});
