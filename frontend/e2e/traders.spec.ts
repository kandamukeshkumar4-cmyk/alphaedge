import { expect, test, type Page, type Route } from "@playwright/test";

import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

const PNL_RANKING = [
  {
    rank: 1,
    username: "north-star",
    realized_pnl: 1840,
    total_trades: 41,
    win_rate: 0.68,
    roi: 0.24,
  },
  {
    rank: 2,
    username: "edge-river",
    realized_pnl: 990,
    total_trades: 37,
    win_rate: 0.62,
    roi: 0.31,
  },
  {
    rank: 3,
    username: "quiet-signal",
    realized_pnl: -120,
    total_trades: 29,
    win_rate: 0.48,
    roi: -0.04,
  },
];

function rankingFor(url: string) {
  const sort = new URL(url).searchParams.get("sort") ?? "realized_pnl";
  const metric =
    sort === "roi"
      ? (entry: (typeof PNL_RANKING)[number]) => entry.roi
      : sort === "win_rate"
        ? (entry: (typeof PNL_RANKING)[number]) => entry.win_rate
        : (entry: (typeof PNL_RANKING)[number]) => entry.realized_pnl;
  return [...PNL_RANKING]
    .sort((left, right) => metric(right) - metric(left))
    .map((entry, index) => ({ ...entry, rank: index + 1 }));
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function routeTraderReads(page: Page, waitForRelease?: Promise<void>) {
  await page.route("**/api/v1/leaderboard**", async (route) => {
    if (waitForRelease) await waitForRelease;
    const url = route.request().url();
    const sort = new URL(url).searchParams.get("sort") ?? "realized_pnl";
    await fulfillJson(route, {
      entries: rankingFor(url),
      limit: 100,
      offset: 0,
      total: PNL_RANKING.length,
      sort,
      cached: false,
    });
  });
  await page.route("**/api/v1/social/traders/*", async (route) => {
    const name = decodeURIComponent(new URL(route.request().url()).pathname.split("/").at(-1) ?? "");
    const entry = PNL_RANKING.find((candidate) => candidate.username === name);
    if (!entry) {
      await fulfillJson(route, { detail: "Trader profile not found" }, 404);
      return;
    }
    await fulfillJson(route, {
      username: entry.username,
      member_since: "2026-01-15T00:00:00Z",
      trade_count: entry.total_trades,
      settled_trade_count: 26,
      win_rate: entry.win_rate,
      roi: entry.roi,
      followers_count: 14,
      following_count: 3,
      paper_trading_only: true,
    });
  });
}

test.describe("Loop 104 live trader surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await page.addInitScript(() => {
      localStorage.setItem("ae_onboarded_v1", "true");
    });
  });

  test("rankings explain the evidence, switch live sort, and remain searchable", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    let releaseReads: () => void = () => {};
    const readsReleased = new Promise<void>((resolve) => {
      releaseReads = resolve;
    });
    await routeTraderReads(page, readsReleased);
    await page.goto("/traders", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("traders-loading")).toBeVisible();
    releaseReads();
    await expect(page.getByRole("heading", { name: "Traders, with receipts" })).toBeVisible();
    await expect(page.getByTestId("trader-row")).toHaveCount(3);
    await expect(page.getByText("Ranked #1 by realized paper p&l", { exact: false })).toBeVisible();

    await page.getByTestId("trader-sort-roi").click();
    await expect(page.getByText("Ranked #1 by return on paper capital", { exact: false })).toBeVisible();
    await expect(page.getByTestId("trader-row").first()).toContainText("edge-river");

    await page.getByLabel("Find a trader").fill("quiet");
    await expect(page.getByTestId("trader-row")).toHaveCount(1);
    await expect(page.getByRole("link", { name: "quiet-signal" })).toHaveAttribute(
      "href",
      "/traders/quiet-signal",
    );

    assertNoConsoleErrors(errors, "/traders");
  });

  test("per-trader detail states exactly why the trader has that rank", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await routeTraderReads(page);
    await page.goto("/traders/edge-river", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByRole("heading", { name: "edge-river" })).toBeVisible();
    await expect(page.getByTestId("trader-detail-rank")).toHaveText("#2");
    await expect(page.getByRole("heading", { name: /\$990 in realized paper P&L/ })).toBeVisible();
    await expect(page.getByText(/Rank 2 comes from settled paper gains/)).toBeVisible();
    await expect(page.getByText("Historical paper performance is descriptive")).toBeVisible();
    await expect(page.getByRole("button", { name: /follow/i })).toHaveCount(0);

    assertNoConsoleErrors(errors, "/traders/edge-river");
  });

  test("an empty live ledger stays honest", async ({ page }) => {
    await page.route("**/api/v1/leaderboard**", (route) =>
      fulfillJson(route, {
        entries: [],
        limit: 100,
        offset: 0,
        total: 0,
        sort: "realized_pnl",
        cached: false,
      }),
    );
    await page.goto("/traders", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("traders-empty")).toBeVisible();
    await expect(page.getByText("No ranked traders yet")).toBeVisible();
    await expect(page.getByTestId("trader-row")).toHaveCount(0);
  });

  test("a live API error renders a retry state instead of sample standings", async ({
    page,
  }) => {
    await page.route("**/api/v1/leaderboard**", (route) =>
      fulfillJson(route, { detail: "temporarily unavailable" }, 503),
    );
    await page.goto("/traders", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("traders-error")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry live ranking" })).toBeVisible();
    await expect(page.getByTestId("trader-row")).toHaveCount(0);
  });
});
