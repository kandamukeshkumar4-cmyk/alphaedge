import { test, expect, type Page, type Route } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * T1 (loop65) — /pods fleet page.
 * Routes live-shape fixtures for GET /api/v1/pods so card / empty / banner
 * assertions stay deterministic on the local stack.
 */

const PODS_PAYLOAD = {
  pods: [
    {
      id: "pod-001",
      name: "nba-momentum",
      status: "running",
      bankroll: 10000,
      equity: 10231.44,
      pnl_24h: 231.44,
      trades_count: 17,
      last_decision_at: "2026-07-17T09:58:00Z",
    },
    {
      id: "pod-002",
      name: "election-mean-revert",
      status: "halted",
      bankroll: 5000,
      equity: 4870.1,
      pnl_24h: -129.9,
      trades_count: 6,
      last_decision_at: null,
    },
  ],
  equity_curves: {
    "pod-001": [
      { t: "2026-07-17T09:00:00Z", equity: 10000 },
      { t: "2026-07-17T09:05:00Z", equity: 10231.44 },
    ],
  },
};

const EMPTY_PODS = { pods: [], equity_curves: {} };

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockPods(page: Page, body: unknown, status = 200) {
  await page.route("**/api/v1/pods", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await fulfillJson(route, body, status);
  });
}

/** Keep the embedded decision terminal from racing the real heartbeat API. */
async function mockDecisionsEmpty(page: Page) {
  await page.route("**/api/v1/heartbeat/decisions**", async (route) => {
    await fulfillJson(route, { decisions: [] });
  });
}

async function visitPods(page: Page) {
  await page.goto("/pods", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
}

test.describe("T1 /pods page", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("pod cards render from mocked GET /api/v1/pods", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await mockPods(page, PODS_PAYLOAD);
    await mockDecisionsEmpty(page);
    await visitPods(page);

    await expect(page.getByRole("heading", { name: /^Pods$/i })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("nba-momentum")).toBeVisible();
    await expect(page.getByText("election-mean-revert")).toBeVisible();
    await expect(page.getByText("pod-001")).toBeVisible();
    await expect(page.getByText("pod-002")).toBeVisible();
    await expect(page.getByText(/^running$/i)).toBeVisible();
    await expect(page.getByText(/^halted$/i)).toBeVisible();
    // formatUSD(10231.44) / formatUSD(4870.1)
    await expect(page.getByText("$10,231.44")).toBeVisible();
    await expect(page.getByText("$4,870.10")).toBeVisible();

    assertNoConsoleErrors(errors, "/pods cards");
  });

  test("honest paper-trading banner is visible", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await mockPods(page, PODS_PAYLOAD);
    await mockDecisionsEmpty(page);
    await visitPods(page);

    await expect(
      page.getByText(/Simulated funds — no execution/i),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByText(/paper-trading telemetry only/i),
    ).toBeVisible();

    assertNoConsoleErrors(errors, "/pods paper banner");
  });

  test("empty state when no pods", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await mockPods(page, EMPTY_PODS);
    await mockDecisionsEmpty(page);
    await visitPods(page);

    await expect(page.getByText(/No pods registered yet/i)).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("nba-momentum")).toHaveCount(0);
    await expect(page.getByText("$10,231.44")).toHaveCount(0);

    assertNoConsoleErrors(errors, "/pods empty");
  });
});
