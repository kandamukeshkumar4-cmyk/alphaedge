import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop 102 (AR1–AR3) — alpha runs / latest-signal / hypotheses UI smoke.
 *
 * The alpha-runs client falls back to a deterministic paper mock when the
 * backend is absent, so /alpha renders fully on a dev-server-only stack:
 * the latest-signal hero (mint when emitted, gray + evidence when
 * withheld — never red), the daily run-history ledger, and the
 * idea-generator hypotheses with VALIDATED / REJECTED verdicts.
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

    // Run history: five seeded daily runs, exactly one emitted a signal
    // (mint YES); withheld rows wear gray NO, never red.
    const history = page.getByTestId("alpha-run-history");
    await expect(history).toBeVisible({ timeout: 20_000 });
    const rows = page.getByTestId("alpha-run-row");
    await expect(rows.first()).toBeVisible();
    await expect(rows).toHaveCount(5);
    await expect(
      rows.filter({ has: page.locator('[data-signal="yes"]') }),
    ).toHaveCount(1);
    await expect(
      rows.filter({ has: page.locator('[data-signal="yes"]') }).first(),
    ).toContainText("Edge confirmed");
    await expect(rows.filter({ hasText: "Portfolio not constructed" })).toHaveCount(1);

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/alpha runs + latest signal");
  });

  test("/alpha renders proposed hypotheses with validated/rejected verdicts", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/alpha", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("alpha-page")).toBeVisible({ timeout: 30_000 });

    const section = page.getByTestId("alpha-hypotheses");
    await expect(section).toBeVisible({ timeout: 20_000 });

    // Four seeded proposals: two validated (mint), two rejected (gray) with
    // the validator's reason on record.
    const rows = page.getByTestId("alpha-hypothesis-row");
    await expect(rows.first()).toBeVisible();
    await expect(rows).toHaveCount(4);
    await expect(rows.filter({ hasText: "VALIDATED" })).toHaveCount(2);
    await expect(rows.filter({ hasText: "REJECTED" })).toHaveCount(2);

    const validatedRow = rows.filter({ hasText: "back_to_back_fade" });
    await expect(validatedRow).toContainText("VALIDATED");
    // Predicted-direction chip (rendered lowercase; CSS uppercases it).
    await expect(validatedRow.getByText("no", { exact: true }).first()).toBeVisible();

    const rejectedRow = rows.filter({ hasText: "injury_overreaction" });
    await expect(rejectedRow).toContainText("REJECTED");
    await expect(rejectedRow).toContainText(/closing line out-of-sample/i);
    // A rejected hypothesis is gray evidence, never a red error.
    await expect(rejectedRow).not.toHaveClass(/danger|error|red/i);

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/alpha hypotheses");
  });
});
