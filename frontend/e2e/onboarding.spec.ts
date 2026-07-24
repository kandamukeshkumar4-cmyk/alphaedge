import { expect, test } from "@playwright/test";

const ONBOARDING_KEY = "ae_onboarded_v1";

test.describe("first-run onboarding", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((key) => {
      window.localStorage.removeItem(key);
    }, ONBOARDING_KEY);
  });

  test("shows the tour and Skip persists completion", async ({ page }) => {
    await page.goto("/");

    const overlay = page.getByTestId("onboarding-overlay");
    await expect(overlay).toBeVisible();
    await expect(overlay).toContainText("AlphaEdge — AI research desk for paper prediction-market trading. Simulated funds only.");

    await overlay.getByRole("button", { name: "Skip" }).click();
    await expect(overlay).toBeHidden();
    await expect.poll(() => page.evaluate((key) => window.localStorage.getItem(key), ONBOARDING_KEY)).toBe("true");
  });
});
