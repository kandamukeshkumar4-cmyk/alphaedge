import { test, expect, type Page, type Route } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { CANONICAL_SLUG } from "./helpers/local-api";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Q1 (loop54) — Locked-forecast panel on market detail.
 * Routes live-shape fixtures for GET /api/v1/markets/{slug}/locked-forecast
 * so locked / provisional / absent states are deterministic on the local stack.
 */

const LOCKED_AT = "2026-07-17T10:00:00Z";

const lockedBody = {
  slug: CANONICAL_SLUG,
  locked: true,
  user_probability: 0.62,
  locked_at: LOCKED_AT,
  market_implied_at_lock: 0.55,
  current_market_probability: 0.58,
  mode: "live",
  provisional: true,
  paper_trading_only: true,
  forecast_id: "11111111-1111-1111-1111-111111111111",
  external_market_id: "22222222-2222-2222-2222-222222222222",
  empty_reason: null,
};

const preLockBody = {
  slug: CANONICAL_SLUG,
  locked: false,
  user_probability: null,
  locked_at: null,
  market_implied_at_lock: null,
  current_market_probability: 0.58,
  mode: null,
  provisional: true,
  paper_trading_only: true,
  forecast_id: null,
  external_market_id: "22222222-2222-2222-2222-222222222222",
  empty_reason: "pre_lock",
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockLockedForecast(page: Page, body: unknown, status = 200) {
  await page.route("**/api/v1/markets/*/locked-forecast", async (route) => {
    await fulfillJson(route, body, status);
  });
}

async function visitMarketDetail(page: Page) {
  await page.goto(`/markets/${CANONICAL_SLUG}`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
}

test.describe("Q1 locked-forecast panel", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("locked state renders user_probability + locked_at and provisional badge", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await mockLockedForecast(page, lockedBody);
    await visitMarketDetail(page);

    const panel = page.getByTestId("locked-forecast-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByText(/^Locked$/i)).toBeVisible();
    await expect(panel.getByText(/^Provisional$/i)).toBeVisible();
    // 0.62 → 62%
    await expect(panel.getByText("62%")).toBeVisible();
    // locked_at rendered as relative time (never invents a bare ISO dump)
    await expect(panel.getByText(/\d+[mhd] ago|just now/i)).toBeVisible();
    await expect(
      panel.getByText(/PROVISIONAL — locked model forecast is not yet CLV-validated/i),
    ).toBeVisible();
    await expect(panel.getByText(/Model: locked/i)).toBeVisible();

    assertNoConsoleErrors(errors, "locked-forecast locked+provisional");
  });

  test("graceful absent (pre-lock) state — no fabricated probability", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await mockLockedForecast(page, preLockBody);
    await visitMarketDetail(page);

    const panel = page.getByTestId("locked-forecast-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByText(/^Pre-lock$/i)).toBeVisible();
    await expect(panel.getByText(/Model forecast locks near close/i)).toBeVisible();
    await expect(panel.getByText(/Model: locked/i)).toHaveCount(0);
    // Must not invent the locked fixture's 62%
    await expect(panel.getByText("62%")).toHaveCount(0);

    assertNoConsoleErrors(errors, "locked-forecast pre-lock");
  });

  test("graceful absent when locked-forecast API is unreachable", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.route("**/api/v1/markets/*/locked-forecast", async (route) => {
      await route.abort("failed");
    });
    await visitMarketDetail(page);

    const panel = page.getByTestId("locked-forecast-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByText(/^Unavailable$/i)).toBeVisible();
    await expect(
      panel.getByText(/Locked forecast unavailable — API not reachable/i),
    ).toBeVisible();
    await expect(panel.getByText(/Model: locked/i)).toHaveCount(0);

    assertNoConsoleErrors(errors, "locked-forecast unavailable");
  });
});
