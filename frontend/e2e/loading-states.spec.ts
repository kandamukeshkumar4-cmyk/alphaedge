import { test, expect, type Route } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import {
  dismissOnboardingIfPresent,
  signupPaperUser,
  skipOnboarding,
  uniqueEmail,
} from "./helpers/session";

/**
 * Q2 (loop54) — Notification bell + /eval loading states.
 * Gate live-shape API responses (same shapes existing journeys consume) so
 * loading copy is observable, then release to honest empty/data.
 */

const EMPTY_NOTIFICATIONS = {
  items: [],
  next_cursor: null,
  limit: 50,
  unread_count: 0,
  paper_trading_only: true,
  disclaimer:
    "In-app notifications only. Simulated funds — no email, SMS, or push delivery.",
};

const EMPTY_DRIFT = {
  series: [],
  count: 0,
  latest_degraded: false,
  paper_trading_only: true,
};

const NOT_RUN_AUTOLAB = {
  ensemble_enabled: false,
  outcome: "not_run",
  baseline_brier: null,
  ensemble_brier: null,
  n_samples: 0,
  notes: "Ensemble comparison has not been run yet.",
};

function deferredGate() {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { gate, release: () => release() };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("Q2 notification bell + /eval loading", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("notification bell shows loading then honest empty", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const errors = collectConsoleErrors(page);

    const { gate, release } = deferredGate();
    // Install before signup so the post-auth remount fetch is gated.
    await page.route("**/api/v1/notifications**", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      await gate;
      await fulfillJson(route, EMPTY_NOTIFICATIONS);
    });

    const email = uniqueEmail("loop54-q2n");
    await signupPaperUser(page, { email, password: "Loop54qa!" });
    await dismissOnboardingIfPresent(page);

    const bell = page.locator("aside").getByRole("button", {
      name: /^Notifications/i,
    });
    await expect(bell).toBeVisible({ timeout: 20_000 });
    await bell.click();

    const center = page.locator('[aria-label="Notification center"]');
    await expect(center).toBeVisible({ timeout: 10_000 });
    await expect(center.getByTestId("notifications-loading")).toBeVisible({
      timeout: 10_000,
    });

    release();

    await expect(
      center.getByText(/You’re all caught up|You're all caught up/i),
    ).toBeVisible({ timeout: 15_000 });
    await expect(center.getByTestId("notifications-loading")).toHaveCount(0);

    assertNoConsoleErrors(errors, "notif bell loading");
  });

  test("/eval shows drift + ensemble loading then honest settle", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const errors = collectConsoleErrors(page);

    const driftGate = deferredGate();
    const autolabGate = deferredGate();

    await page.route("**/api/v1/eval/drift**", async (route) => {
      await driftGate.gate;
      await fulfillJson(route, EMPTY_DRIFT);
    });
    await page.route("**/api/v1/ensemble/autolab**", async (route) => {
      await autolabGate.gate;
      await fulfillJson(route, NOT_RUN_AUTOLAB);
    });

    await page.goto("/eval", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    await expect(
      page.getByRole("heading", { name: /Proof dashboard/i }),
    ).toBeVisible({ timeout: 20_000 });

    const drift = page.getByTestId("drift-series-panel");
    await expect(drift).toBeVisible({ timeout: 20_000 });
    await expect(drift.getByText(/Loading drift snapshots…/i)).toBeVisible({
      timeout: 10_000,
    });

    const ensemble = page.getByTestId("ensemble-autolab-section");
    await expect(ensemble).toBeVisible();
    await expect(ensemble.getByText(/^Loading…$/i)).toBeVisible({
      timeout: 10_000,
    });

    driftGate.release();
    autolabGate.release();

    await expect(drift.getByText(/No drift snapshots yet/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("ensemble-not-measured")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByTestId("ensemble-not-measured").getByText(/Not yet measured/i),
    ).toBeVisible();

    assertNoConsoleErrors(errors, "/eval loading");
  });
});
