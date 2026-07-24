import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V92 (PU3) — portfolio Analytics tab smoke.
 * Seeds a paper JWT + stubs GET /api/v1/portfolio so the page shell renders
 * without a live backend. Analytics client falls back to its PAPER mock
 * (stats + equity + calibration) — same dev-server-only path as V79/V85.
 */

const ACCESS_TOKEN_KEY = "alphaedge.accessToken";
const USER_EMAIL_KEY = "alphaedge.userEmail";
const ONBOARDING_KEY = "ae_onboarded_v1";
const COACHMARKS_KEY = "alphaedge.coachmarks.v1";

const EMPTY_PORTFOLIO = {
  paper_balance: 100_000,
  positions: [],
  realized_pnl: 0,
  unrealized_pnl: 0,
  portfolio_value: 100_000,
  total_trades: 0,
  paper_trading_only: true,
  disclaimer:
    "Research only — not financial advice. Verify resolution terms. Paper trading only.",
};

const PREEXISTING_MARKETS_PROBE_NOISE = /Markets HTTP 503/;

test.describe("V92 portfolio analytics", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await page.addInitScript(
      ({ tokenKey, emailKey, onboardKey, coachKey }) => {
        try {
          localStorage.setItem(tokenKey, "e2e-paper-jwt");
          localStorage.setItem(emailKey, "analytics-e2e@example.com");
          localStorage.setItem(onboardKey, "true");
          localStorage.setItem(coachKey, "true");
        } catch {
          /* ignore */
        }
      },
      {
        tokenKey: ACCESS_TOKEN_KEY,
        emailKey: USER_EMAIL_KEY,
        onboardKey: ONBOARDING_KEY,
        coachKey: COACHMARKS_KEY,
      },
    );

    // Portfolio shell requires a successful GET /api/v1/portfolio; analytics
    // itself uses the client mock when the analytics endpoint is absent.
    await page.route("**/api/v1/portfolio", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const path = new URL(route.request().url()).pathname.replace(/\/+$/, "");
      if (path !== "/api/v1/portfolio") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(EMPTY_PORTFOLIO),
      });
    });

    await page.route("**/api/v1/portfolio/orders**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ paper_balance: 100_000 }),
      });
    });

    // Force analytics onto the seeded PAPER mock (deterministic e2e).
    await page.route("**/api/v1/portfolio/analytics**", async (route) => {
      await route.fulfill({ status: 503, body: "unavailable" });
    });
  });

  test("Analytics tab shows paper stats, equity curve, and calibration", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    const overlay = page.getByTestId("onboarding-overlay");
    if (await overlay.isVisible({ timeout: 1500 }).catch(() => false)) {
      await overlay.getByRole("button", { name: /^Skip$/i }).click();
      await expect(overlay).toHaveCount(0);
    }

    await expect(page.getByRole("heading", { name: "Portfolio" })).toBeVisible({
      timeout: 30_000,
    });

    await page.getByTestId("portfolio-tab-analytics").click();
    await expect(page.getByTestId("portfolio-analytics")).toBeVisible({
      timeout: 20_000,
    });

    await expect(page.getByTestId("analytics-days-selector")).toBeVisible();
    await expect(page.getByTestId("analytics-stat-card")).toHaveCount(4);
    await expect(page.getByTestId("analytics-equity-chart")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "Paper calibration" })).toBeVisible();
    await expect(page.getByTestId("analytics-calibration")).toBeVisible();
    await expect(page.getByTestId("analytics-calibration-bars")).toBeVisible();

    // Days selector is interactive (7/30/90).
    await page.getByRole("button", { name: "7d" }).click();
    await expect(page.getByTestId("portfolio-analytics")).toBeVisible();

    await page.waitForTimeout(500);
    assertNoConsoleErrors(
      errors.filter((e) => !PREEXISTING_MARKETS_PROBE_NOISE.test(e)),
      "/portfolio analytics",
    );
  });
});
