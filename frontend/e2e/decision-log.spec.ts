import { test, expect, type Page, type Route } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * T2 (loop65) — decision-log terminal on /pods.
 * Routes live-shape fixtures for GET /api/v1/heartbeat/decisions so row /
 * action-color / empty assertions stay deterministic on the local stack.
 */

const DECISIONS_PAYLOAD = {
  decisions: [
    {
      t: "2026-07-17T10:00:00Z",
      pod: "nba-momentum",
      market: "nba-2025-01-15-lal-bos",
      rule: "edge_threshold",
      action: "buy_yes",
      latency_ms: 182,
    },
    {
      t: "2026-07-17T09:59:00Z",
      pod: "election-mean-revert",
      market: "election-2024-pres",
      rule: "stop_loss",
      action: "sell_no",
      latency_ms: 95,
    },
    {
      t: "2026-07-17T09:58:00Z",
      pod: "nba-momentum",
      market: "nba-2025-01-15-lal-bos",
      rule: "cooldown",
      action: "skip",
      latency_ms: 12,
    },
  ],
};

const EMPTY_DECISIONS = { decisions: [] };

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/** Keep fleet cards from racing the real pods API. */
async function mockPodsEmpty(page: Page) {
  await page.route("**/api/v1/pods", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await fulfillJson(route, { pods: [], equity_curves: {} });
  });
}

async function mockDecisions(page: Page, body: unknown, status = 200) {
  await page.route("**/api/v1/heartbeat/decisions**", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await fulfillJson(route, body, status);
  });
}

async function visitPods(page: Page) {
  await page.goto("/pods", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
}

function decisionLog(page: Page) {
  return page.getByRole("region", { name: /Pod decision log/i });
}

test.describe("T2 decision-log terminal", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("rows render from mocked GET /api/v1/heartbeat/decisions", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await mockPodsEmpty(page);
    await mockDecisions(page, DECISIONS_PAYLOAD);
    await visitPods(page);

    const terminal = decisionLog(page);
    await expect(terminal).toBeVisible({ timeout: 30_000 });
    await expect(terminal.getByText("buy_yes")).toBeVisible();
    await expect(terminal.getByText("sell_no")).toBeVisible();
    await expect(terminal.getByText("skip")).toBeVisible();
    await expect(terminal.getByText("edge_threshold")).toBeVisible();
    await expect(terminal.getByText("stop_loss")).toBeVisible();
    await expect(terminal.getByText("nba-2025-01-15-lal-bos").first()).toBeVisible();
    // Newest-first timestamps (UTC HH:MM:SS)
    await expect(terminal.getByText("10:00:00")).toBeVisible();
    await expect(terminal.getByText("09:59:00")).toBeVisible();

    assertNoConsoleErrors(errors, "decision-log rows");
  });

  test("action colors use buy/sell trade tokens", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await mockPodsEmpty(page);
    await mockDecisions(page, DECISIONS_PAYLOAD);
    await visitPods(page);

    const terminal = decisionLog(page);
    await expect(terminal).toBeVisible({ timeout: 30_000 });

    const buyBadge = terminal.locator("span").filter({ hasText: /^buy_yes$/i });
    const sellBadge = terminal.locator("span").filter({ hasText: /^sell_no$/i });
    const skipBadge = terminal.locator("span").filter({ hasText: /^skip$/i });

    await expect(buyBadge).toBeVisible();
    await expect(sellBadge).toBeVisible();
    await expect(skipBadge).toBeVisible();

    await expect(buyBadge).toHaveClass(/text-primary/);
    await expect(sellBadge).toHaveClass(/text-danger/);
    await expect(skipBadge).toHaveClass(/text-muted/);

    assertNoConsoleErrors(errors, "decision-log action colors");
  });

  test("empty state when no decisions", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await mockPodsEmpty(page);
    await mockDecisions(page, EMPTY_DECISIONS);
    await visitPods(page);

    const terminal = decisionLog(page);
    await expect(terminal).toBeVisible({ timeout: 30_000 });
    await expect(
      terminal.getByText(/No decisions logged yet/i),
    ).toBeVisible();
    await expect(terminal.getByText("buy_yes")).toHaveCount(0);
    await expect(terminal.getByRole("list")).toHaveCount(0);

    assertNoConsoleErrors(errors, "decision-log empty");
  });
});
