import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V84 U4 — Scanner Studio smoke.
 * The scanners client falls back to its in-memory PAPER mock when the live
 * API is absent/empty, so the list, the compile preview and the detail
 * canvas all render without the backend.
 */
test.describe("V84 Scanner Studio", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/scanners renders the list from mock and a compile preview appears", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("scanners-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Scanners", exact: true })).toBeVisible();
    await expect(page.getByTestId("scanners-paper-banner")).toBeVisible();

    // Mock store seeds three scanners (active / paused / draft).
    const cards = page.getByTestId("scanner-card");
    await expect(cards.first()).toBeVisible({ timeout: 20_000 });
    expect(await cards.count()).toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("scanner-status-pill").first()).toBeVisible();

    // Composer flow: describe → compile → spec preview with step chips.
    await page
      .getByTestId("scanners-request-input")
      .fill("Scan NBA markets with whale flow and price trend every 15 minutes, volume above 50,000");
    await page.getByTestId("scanners-compile").click();
    await expect(page.getByTestId("scanners-preview")).toBeVisible({ timeout: 20_000 });
    const chips = page.getByTestId("scanners-preview-steps").locator("li");
    await expect(chips.first()).toBeVisible();
    expect(await chips.count()).toBeGreaterThanOrEqual(2);

    assertNoConsoleErrors(errors, "/scanners");
  });

  test("scanner detail renders the pipeline canvas with >=3 nodes", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanner-card").first()).toBeVisible({ timeout: 20_000 });

    // Seeded mock scanner with a 5-step spec (unknown id live → mock fallback).
    await page.goto("/scanners/scn-mock-whale", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByTestId("scanner-detail-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("scanner-detail-paper-banner")).toBeVisible();
    await expect(page.getByTestId("scanner-canvas")).toBeVisible({ timeout: 20_000 });

    const nodes = page.locator(".react-flow__node");
    await expect(async () => {
      expect(await nodes.count()).toBeGreaterThanOrEqual(3);
    }).toPass({ timeout: 15_000 });
    await expect(page.getByTestId("scanner-step-node").first()).toBeVisible();

    // Latest run panel + runs history render.
    await expect(page.getByTestId("scanner-latest-run")).toBeVisible();
    await expect(page.getByTestId("scanner-candidates")).toBeVisible();
    await expect(page.getByTestId("scanner-runs-history")).toBeVisible();

    assertNoConsoleErrors(errors, "/scanners/[id]");
  });

  test("draft scanner shows the Test & publish panel and version chip", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners/scn-mock-draft", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanner-detail-page")).toBeVisible({ timeout: 30_000 });

    // X1 — pre-publish panel on a draft scanner.
    await expect(page.getByTestId("scanner-prepublish")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scanner-test-run")).toBeVisible();
    await expect(page.getByTestId("scanner-test-email")).toBeVisible();
    await expect(page.getByTestId("scanner-publish")).toBeVisible();
    // Publish is locked until a test run exists.
    await expect(page.getByTestId("scanner-publish")).toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("scanner-test-result")).toHaveCount(0);

    // Run a test -> the test result appears with the TEST RUN badge.
    await page.getByTestId("scanner-test-run").click();
    await expect(page.getByTestId("scanner-test-result")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scanner-test-candidates")).toBeVisible();
    await expect(page.getByTestId("scanner-publish")).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );

    // Send a test email -> not-configured toast (the draft spec has email off).
    await page.getByTestId("scanner-test-email").click();
    await expect(page.getByText("Email not configured")).toBeVisible({ timeout: 10_000 });

    // Publish -> status flips to active (status pill carries data-status).
    await page.getByTestId("scanner-publish").click();
    await expect(page.getByTestId("scanner-status-pill")).toHaveAttribute(
      "data-status",
      "active",
      { timeout: 15_000 },
    );

    assertNoConsoleErrors(errors, "/scanners/[id] draft");
  });

  test("active scanner shows the version chip with rollback history", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners/scn-mock-whale", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanner-detail-page")).toBeVisible({ timeout: 30_000 });

    // X2 — version chip opens a history popover with older-version rollback.
    await expect(page.getByTestId("scanner-version-chip")).toBeVisible();
    await page.getByTestId("scanner-version-chip").click();
    await expect(page.getByTestId("scanner-version-popover")).toBeVisible({ timeout: 10_000 });
    const versionRows = page.getByTestId("scanner-version-row");
    await expect(versionRows.first()).toBeVisible();
    expect(await versionRows.count()).toBeGreaterThan(1);
    await expect(page.getByTestId("scanner-rollback").first()).toBeVisible();

    // X2 — Run-again affordance on the latest-run result panel.
    await expect(page.getByTestId("scanner-run-again")).toBeVisible();

    assertNoConsoleErrors(errors, "/scanners/[id] versions");
  });

  test("Run now shows the build narration rail (X3)", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners/scn-mock-whale", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanner-detail-page")).toBeVisible({ timeout: 30_000 });

    // No narration before a run.
    await expect(page.getByTestId("scanner-build-narration")).toHaveCount(0);
    await page.getByTestId("scanner-detail-run").click();
    await expect(page.getByTestId("scanner-build-narration")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("scanner-build-narration-step").first()).toBeVisible();

    assertNoConsoleErrors(errors, "/scanners/[id] narration");
  });
});
