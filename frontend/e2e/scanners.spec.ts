import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V84 U4 — Scanner Studio smoke.
 * The scanners client falls back to its in-memory PAPER mock when the live
 * API is absent/empty, so the list, the compile preview and the detail
 * canvas all render without the backend.
 *
 * Loop V88 (V3) — DOM assertions for the self-heal repairs chip + ledger
 * (V1) and the compile badge + warnings (V2), driven by the mock client's
 * seeded `repairs` and deterministic `warnings` fields.
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

    // loop116 — the run artifact is LIVE-ONLY on purpose: this spec runs on the
    // in-memory mock, so no document may appear. Fabricating a fired dashboard
    // is exactly what this surface exists to replace. The step list below it
    // must be unaffected (asserted above).
    await expect(page.getByTestId("scanner-run-artifact")).toHaveCount(0);

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

  test("V1 — self-heal repairs chip + ledger on the latest run, count chips on history rows", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners/scn-mock-whale", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanner-detail-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("scanner-latest-run")).toBeVisible({ timeout: 20_000 });

    // The seeded latest run (run-mock-whale-2) carries two repairs.
    const chip = page.getByTestId("scanner-selfheal-chip");
    await expect(chip).toBeVisible();
    await expect(chip).toHaveText(/Self-healed x2/);
    await expect(chip).toHaveAttribute("data-count", "2");
    await expect(chip).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("scanner-repair-ledger")).toHaveAttribute(
      "aria-hidden",
      "true",
    );

    // Expanding lists each repair as "<node>: <class> -> <action>" in mono.
    await chip.click();
    await expect(chip).toHaveAttribute("aria-expanded", "true");
    const ledger = page.getByTestId("scanner-repair-ledger");
    await expect(ledger).toHaveAttribute("aria-hidden", "false");
    await expect(ledger).toBeVisible();
    const rows = page.getByTestId("scanner-repair-row");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toHaveText(/1: rate_limited -> sleep_retry/);
    await expect(rows.nth(1)).toHaveText(/3: type_mismatch -> coerce_numeric/);

    // Collapse again — the ledger hides from assistive tech.
    await chip.click();
    await expect(chip).toHaveAttribute("aria-expanded", "false");
    await expect(ledger).toHaveAttribute("aria-hidden", "true");

    // Runs history (newest first): whale-2 healed x2, whale-1 healed x1.
    const historyChips = page
      .getByTestId("scanner-runs-history")
      .getByTestId("scanner-run-repairs");
    await expect(historyChips).toHaveCount(2);
    await expect(historyChips.nth(0)).toHaveAttribute("data-count", "2");
    await expect(historyChips.nth(1)).toHaveAttribute("data-count", "1");

    assertNoConsoleErrors(errors, "/scanners/[id] repairs (V1)");
  });

  test("V2 — compile badge + warnings in the describe-a-scanner preview", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanners-page")).toBeVisible({ timeout: 30_000 });

    // Benign compile (15-min interval, 3 steps): deterministic badge, no warnings.
    await page
      .getByTestId("scanners-request-input")
      .fill("Scan NBA markets with whale flow and price trend every 15 minutes, volume above 50,000");
    await page.getByTestId("scanners-compile").click();
    await expect(page.getByTestId("scanners-preview")).toBeVisible({ timeout: 20_000 });
    const badge = page.getByTestId("scanners-compiler-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveAttribute("data-compiler", "deterministic");
    await expect(badge).toHaveText(/Compiled: deterministic/);
    await expect(page.getByTestId("scanners-compile-warnings")).toHaveCount(0);

    // Spend-warning compile (5-min interval, 5 steps): amber warnings above Create.
    await page
      .getByTestId("scanners-request-input")
      .fill(
        "Scan NBA markets with whale flow, price trend, news sentiment and model edge every 5 minutes",
      );
    await page.getByTestId("scanners-compile").click();
    const warnings = page.getByTestId("scanners-compile-warnings");
    await expect(warnings).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scanners-compile-warning")).toHaveCount(1);
    await expect(page.getByTestId("scanners-compile-warning")).toHaveText(
      /spend warning: interval under 15 minutes with more than 3 steps/,
    );
    // Mock compile stays on the deterministic path — badge unchanged.
    await expect(badge).toHaveAttribute("data-compiler", "deterministic");

    // Warnings render above the Create button.
    const warningsBox = await warnings.boundingBox();
    const createBox = await page.getByTestId("scanners-create").boundingBox();
    expect(warningsBox).not.toBeNull();
    expect(createBox).not.toBeNull();
    expect(warningsBox!.y + warningsBox!.height).toBeLessThanOrEqual(createBox!.y + 1);

    assertNoConsoleErrors(errors, "/scanners compile feedback (V2)");
  });

  test("loop116 — clarify → answer → ready → testfire renders", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/scanners", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("scanners-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("onboarding-overlay")).toHaveCount(0);

    // Ambiguous prompt → clarifying questions (schedule + threshold + delivery).
    const input = page.getByTestId("scanners-request-input");
    await input.click();
    await input.fill("");
    await input.pressSequentially(
      "Alert me about big NBA whale flow movers soon",
      { delay: 8 },
    );
    await expect(input).toHaveValue(/Alert me about big NBA/);
    await expect(page.getByTestId("scanners-compile")).toBeEnabled();
    await page.getByTestId("scanners-compile").click();
    await expect(page.getByTestId("scanners-clarify")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scanners-authoring-chat")).toBeVisible();
    await expect(page.getByTestId("scanners-clarify-question").first()).toBeVisible();

    // Click suggestions for each pending question, then submit.
    const questions = page.getByTestId("scanners-clarify-question");
    const count = await questions.count();
    for (let i = 0; i < count; i += 1) {
      const q = questions.nth(i);
      await q.getByTestId("scanners-clarify-suggestion").first().click();
    }
    await page.getByTestId("scanners-clarify-submit").click();

    // May need a second round — answer again if clarify still visible.
    await page.waitForTimeout(400);
    if (await page.getByTestId("scanners-clarify").isVisible().catch(() => false)) {
      const q2 = page.getByTestId("scanners-clarify-question");
      const n2 = await q2.count();
      for (let i = 0; i < n2; i += 1) {
        await q2.nth(i).getByTestId("scanners-clarify-suggestion").first().click();
      }
      await page.getByTestId("scanners-clarify-submit").click();
    }

    await expect(page.getByTestId("scanners-preview")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scanners-testfire")).toBeVisible();
    await page.getByTestId("scanners-testfire").click();
    await expect(page.getByTestId("scanners-testfire-result")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scanners-testfire-matches")).toBeVisible();
    await expect(page.getByTestId("scanners-create")).toBeVisible();

    assertNoConsoleErrors(errors, "/scanners conversational authoring");
  });
});
