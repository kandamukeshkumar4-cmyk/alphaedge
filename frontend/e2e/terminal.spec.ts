import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V79 A5 — Research Terminal smoke.
 * Mock client seeds a completed Lakers/Celtics session so the page renders
 * step cards + scoreboard without the backend stream.
 */
test.describe("V79 terminal", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/terminal renders a session with steps and scoreboard", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/terminal", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("terminal-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /Research Terminal/i })).toBeVisible();
    await expect(page.getByTestId("terminal-paper-banner")).toBeVisible();
    await expect(page.getByTestId("terminal-session-sidebar")).toBeVisible();
    await expect(page.getByTestId("terminal-composer")).toBeVisible();
    await expect(page.getByTestId("terminal-sense-chips")).toBeVisible();

    const step = page.getByTestId("terminal-step-card").first();
    await expect(step).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("terminal-scoreboard")).toBeVisible();
    await expect(page.getByTestId("terminal-bull-bear")).toBeVisible();

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/terminal");
  });
});
