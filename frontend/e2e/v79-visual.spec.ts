import { test } from "@playwright/test";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/** TEMP A7 visual check — screenshots home (nav+hero) and /terminal. */
test.describe("A7 visual", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    // Shots capture the seeded MOCK terminal session — force the offline
    // mock path (the local-stack terminal API requires auth, honest empty).
    await page.route("**/api/v1/terminal/**", (route) => route.abort());
  });

  test("shots", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: "test-results/a7-home.png", fullPage: false });

    await page.goto("/terminal", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await page.getByTestId("terminal-step-card").first().waitFor({ timeout: 20_000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: "test-results/a7-terminal.png", fullPage: false });

    await page.getByTestId("terminal-view-canvas").click();
    await page.getByTestId("terminal-canvas").waitFor({ timeout: 15_000 });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: "test-results/a7-canvas.png", fullPage: false });
  });
});
