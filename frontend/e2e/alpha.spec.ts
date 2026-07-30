import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop 99 (AU1–AU3) — alpha model + TA indicators UI smoke.
 *
 * The alpha/indicators clients fall back to a deterministic paper mock when
 * the backend is absent, so both surfaces render fully on a dev-server-only
 * stack: the /alpha factor ledger + validated-factor report, and the TA
 * panel (regime chip, indicator tiles, close + SMA-20 chart) on the market
 * detail page.
 */
test.describe("Loop99 alpha UI", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/alpha renders the factor ledger and validated-factor report", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    // Force the documented "backend absent → deterministic paper mock" path:
    // against a live local stack the API returns honest-empty factor data,
    // which is correct UI behaviour but not what this mock-rendering smoke
    // asserts (7 seeded factors, momentum killed by the CLV validator).
    await page.route("**/api/v1/alpha/**", (route) =>
      route.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
    await page.goto("/alpha", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("alpha-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /Multi-Factor Alpha/i })).toBeVisible();
    await expect(page.getByTestId("alpha-paper-banner")).toBeVisible();
    await expect(page.getByTestId("alpha-source-badge")).toBeVisible();

    // Seven seeded factors render with VALID / KILLED badges (gray, not red).
    const rows = page.getByTestId("alpha-factor-row");
    await expect(rows.first()).toBeVisible({ timeout: 20_000 });
    await expect(rows).toHaveCount(7);
    await expect(rows.filter({ hasText: "model_edge" }).first()).toContainText("VALID");
    await expect(rows.filter({ hasText: "momentum" }).first()).toContainText("KILLED");
    // A killed factor explains why (human-readable validator reason).
    await expect(rows.filter({ hasText: "momentum" }).first()).toContainText(
      /closing line out-of-sample/i,
    );

    // Validated-factor report card: survivors + killed-by-validator list.
    await expect(page.getByTestId("alpha-report-card")).toBeVisible();
    await expect(page.getByTestId("alpha-report-valid-row").first()).toBeVisible();
    await expect(page.getByTestId("alpha-report-killed-row").first()).toBeVisible();

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/alpha");
  });

  test("market detail shows the TA indicators panel with regime + chart", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/markets/nba-2025-01-15-lal-bos", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    const panel = page.getByTestId("indicators-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });

    // Regime chip carries the backend regime code; chart + tiles render.
    const chip = page.getByTestId("indicators-regime-chip");
    await expect(chip).toBeVisible();
    await expect(chip).toHaveAttribute("data-regime", /.+/);
    await expect(panel.getByTestId("indicators-chart")).toBeVisible();
    await expect(panel.getByTestId("indicators-tile-rsi")).toBeVisible();
    await expect(panel.getByTestId("indicators-tile-macd")).toBeVisible();
    await expect(panel.getByTestId("indicators-tile-adx")).toBeVisible();

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "/markets/[slug] TA panel");
  });
});
