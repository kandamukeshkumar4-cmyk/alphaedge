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
    // These smokes verify the seeded MOCK session ("without the backend
    // stream"). The local-stack backend's terminal API requires auth and
    // returns an honest signed-out state — force the offline mock path.
    await page.route("**/api/v1/terminal/**", (route) => route.abort());
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

  test("A6 canvas view renders the session node graph", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/terminal", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    // Wait for the auto-loaded session so step nodes exist.
    await expect(page.getByTestId("terminal-step-card").first()).toBeVisible({
      timeout: 20_000,
    });

    await page.getByTestId("terminal-view-canvas").click();
    await expect(page.getByTestId("terminal-canvas")).toBeVisible({ timeout: 15_000 });

    // 5 mock steps + 1 Final Results node.
    await expect(page.locator(".react-flow__node")).toHaveCount(6, { timeout: 15_000 });
    await expect(page.getByText(/Final results/i)).toBeVisible();

    // Node click returns to the Dashboard tab.
    await page.locator(".react-flow__node").first().click();
    await expect(page.getByTestId("terminal-session-body")).toBeVisible();

    assertNoConsoleErrors(errors, "/terminal canvas");
  });
});
