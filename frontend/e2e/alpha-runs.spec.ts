import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Alpha runs / latest-signal / hypotheses UI smoke.
 *
 * Asserts the REAL rendered truth from the local stack: honest empty states
 * when the research tail has no rows, or real rows when the API returns them.
 * Never asserts fabricated seed counts (the old five-row / four-hypothesis
 * mock contract is gone).
 */
test.describe("Loop102 alpha runs UI", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/alpha renders the latest-signal hero and run history", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/alpha", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("alpha-page")).toBeVisible({ timeout: 30_000 });

    // Hero carries an emitted flag; headline is mint-edge or gray-withheld.
    const hero = page.getByTestId("alpha-latest-signal");
    await expect(hero).toBeVisible({ timeout: 20_000 });
    await expect(hero).toHaveAttribute("data-emitted", /^(true|false)$/);
    const headline = page.getByTestId("alpha-latest-signal-headline");
    await expect(headline).toBeVisible();
    await expect(headline).toHaveText(/Edge found, t-stat \d\.\d|No signal today/);

    // A withheld signal explains itself — evidence line is never empty,
    // and the hero never wears the danger palette.
    if ((await hero.getAttribute("data-emitted")) === "false") {
      await expect(page.getByTestId("alpha-latest-signal-evidence")).toContainText(
        /evidence:/i,
      );
      await expect(hero).not.toHaveClass(/danger|error|red/i);
    } else {
      await expect(page.getByTestId("alpha-latest-signal-weights")).toBeVisible();
    }

    // Run history: honest empty OR real rows from the local stack — never
    // invent a five-seed ledger.
    const history = page.getByTestId("alpha-run-history");
    await expect(history).toBeVisible({ timeout: 20_000 });
    const empty = page.getByTestId("alpha-runs-empty-state");
    const rows = page.getByTestId("alpha-run-row");
    if (await empty.isVisible()) {
      await expect(empty).toContainText(/No research runs yet/i);
      await expect(rows).toHaveCount(0);
    } else {
      await expect(rows.first()).toBeVisible();
      const count = await rows.count();
      expect(count).toBeGreaterThan(0);
      // Every row carries a yes|no signal badge (mint YES / gray NO).
      for (let i = 0; i < count; i++) {
        await expect(rows.nth(i).locator("[data-signal]")).toHaveAttribute(
          "data-signal",
          /^(yes|no)$/,
        );
      }
      // Must not claim a fabricated "Edge confirmed" when nothing emitted.
      const emitted = rows.filter({ has: page.locator('[data-signal="yes"]') });
      const emittedCount = await emitted.count();
      if (emittedCount > 0) {
        await expect(emitted.first()).toContainText(/Edge confirmed|genuine/i);
      }
    }

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/alpha runs + latest signal");
  });

  test("/alpha renders hypotheses section (honest empty or real verdicts)", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/alpha", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("alpha-page")).toBeVisible({ timeout: 30_000 });

    const section = page.getByTestId("alpha-hypotheses");
    await expect(section).toBeVisible({ timeout: 20_000 });

    // Honest empty OR real proposal rows — never assert the old four-seed board.
    const empty = page.getByTestId("alpha-hypotheses-empty-state");
    const rows = page.getByTestId("alpha-hypothesis-row");
    if (await empty.isVisible()) {
      await expect(empty).toContainText(/No hypotheses proposed yet/i);
      await expect(rows).toHaveCount(0);
    } else {
      await expect(rows.first()).toBeVisible();
      const count = await rows.count();
      expect(count).toBeGreaterThan(0);
      // Each row wears VALIDATED or REJECTED (never red).
      for (let i = 0; i < count; i++) {
        const row = rows.nth(i);
        await expect(row).toHaveAttribute("data-validated", /^(true|false)$/);
        if ((await row.getAttribute("data-validated")) === "true") {
          await expect(row).toContainText("VALIDATED");
        } else {
          await expect(row).toContainText("REJECTED");
        }
        await expect(row).not.toHaveClass(/danger|error|red/i);
      }
    }

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/alpha hypotheses");
  });
});
