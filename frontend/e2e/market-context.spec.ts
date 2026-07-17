import { test, expect, type Page, type Route } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { CANONICAL_SLUG } from "./helpers/local-api";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * T3 (loop65) — market context panel on market detail.
 * Routes live-shape fixtures for GET /api/v1/markets/{slug}/context so whale
 * gauge / venue gap / absent states stay deterministic on the local stack.
 */

const CONTEXT_PAYLOAD = {
  whale_pressure: 0.72,
  venue_gap: 0.015,
  news_signal: 0.4,
  price_trend: 0.06,
  volume_pct: 0.81,
  captured_at: "2026-07-17T10:01:00Z",
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockMarketContext(page: Page, body: unknown, status = 200) {
  await page.route("**/api/v1/markets/*/context", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
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

function contextPanel(page: Page) {
  return page.getByRole("region", { name: /Market context/i });
}

test.describe("T3 market context panel", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("whale gauge + venue gap render from mocked context", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await mockMarketContext(page, CONTEXT_PAYLOAD);
    await visitMarketDetail(page);

    const panel = contextPanel(page);
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByText(/Whale pressure/i)).toBeVisible();
    const gauge = panel.getByRole("meter", { name: /Whale pressure/i });
    await expect(gauge).toBeVisible();
    await expect(gauge).toHaveAttribute("aria-valuenow", "72");
    await expect(panel.getByText(/heavy/i)).toBeVisible();
    await expect(panel.getByText(/Venue gap/i)).toBeVisible();
    await expect(panel.getByText("+1.5¢")).toBeVisible();
    await expect(panel.getByText(/News tone/i)).toBeVisible();
    await expect(panel.getByText(/^positive$/i)).toBeVisible();
    await expect(panel.getByText("+6.0%")).toBeVisible();
    await expect(panel.getByText("81%")).toBeVisible();
    await expect(panel.getByText(/not trading advice/i)).toBeVisible();

    assertNoConsoleErrors(errors, "market-context populated");
  });

  test("absent state when context API returns 404", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await mockMarketContext(page, { detail: "Not Found" }, 404);
    await visitMarketDetail(page);

    const panel = contextPanel(page);
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(
      panel.getByText(/Market context not yet deployed/i),
    ).toBeVisible();
    await expect(panel.getByRole("meter")).toHaveCount(0);
    await expect(panel.getByText("+1.5¢")).toHaveCount(0);
    await expect(panel.getByText(/Whale pressure/i)).toHaveCount(0);

    assertNoConsoleErrors(errors, "market-context 404");
  });

  test("absent state when context API is unreachable", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.route("**/api/v1/markets/*/context", async (route) => {
      await route.abort("failed");
    });
    await visitMarketDetail(page);

    const panel = contextPanel(page);
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByText(/Market context unavailable/i)).toBeVisible();
    await expect(panel.getByRole("meter")).toHaveCount(0);
    await expect(panel.getByText("+1.5¢")).toHaveCount(0);

    assertNoConsoleErrors(errors, "market-context unavailable");
  });
});
