import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V91 SU3 — command-palette search E2E.
 *
 * Runs against a dev server whose NEXT_PUBLIC_API_URL points at a dead port,
 * so searchMarkets live-first fetch fails fast and every row below comes
 * from the deterministic PAPER mock catalog in src/lib/search-api.ts.
 * DOM assertions only — no screenshots.
 */

const CANONICAL_TITLE = "Lakers vs Celtics — Jan 15 Tip-Off";
const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

/**
 * Dead-port environment noise: the app's health/WS polling produces an
 * unhandled "Failed to fetch" rejection on idle page load (fires before any
 * search interaction — pre-existing, unrelated to the palette). Filter it
 * here, keep React console errors strict via the shared helper.
 */
const ENV_NOISE = /^pageerror: Failed to fetch$/;

async function openPaletteViaHotkey(page: Page) {
  // Retry the hotkey until hydration has attached the window listener —
  // a press before React mounts is a no-op, not a failure.
  for (let attempt = 0; attempt < 6; attempt++) {
    await page.keyboard.press("ControlOrMeta+KeyK");
    if (await page.getByTestId("search-palette").isVisible()) return;
    await page.waitForTimeout(300);
  }
  await expect(page.getByTestId("search-palette")).toBeVisible();
}

async function openPaletteViaTriggerClick(page: Page) {
  // Same hydration guard: an early click lands before React attaches the
  // handler, so click-and-check until the palette actually opens.
  const trigger = page.getByTestId("search-trigger");
  for (let attempt = 0; attempt < 8; attempt++) {
    await trigger.click();
    if (await page.getByTestId("search-palette").isVisible()) return;
    await page.waitForTimeout(400);
  }
  await expect(page.getByTestId("search-palette")).toBeVisible();
}

test.describe("V91 search palette", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    // Current onboarding gate key (lib/onboarding.ts) — the shared helper
    // only seeds the legacy key, so seed the live one too.
    await page.addInitScript(() => {
      try {
        localStorage.setItem("ae_onboarded_v1", "true");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByTestId("search-trigger")).toBeVisible({ timeout: 30_000 });
  });

  test("Cmd/Ctrl-K opens the palette focused on the input; ESC closes it", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);

    await openPaletteViaHotkey(page);
    await expect(page.getByTestId("search-input")).toBeFocused();
    // No query yet → the idle empty state with the shortcut legend.
    await expect(page.getByTestId("search-empty-state")).toBeVisible();
    await expect(page.getByTestId("search-result-item")).toHaveCount(0);

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("search-palette")).toBeHidden();

    assertNoConsoleErrors(errors.filter((e) => !ENV_NOISE.test(e)), "palette open/close");
  });

  test("typing shows paper mock results after the debounce", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    // This test verifies the PAPER mock fallback + honest source chip, so the
    // live search API must be unreachable — in the local-stack CI the backend
    // is actually up, which would return live rows instead.
    await page.route("**/api/v1/search**", (route) => route.abort());

    await openPaletteViaHotkey(page);
    const input = page.getByTestId("search-input");
    await input.pressSequentially("Lakers", { delay: 20 });

    // Debounce (200ms) + mock fallback resolves into real rows.
    await expect(page.getByTestId("search-result-item").first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(CANONICAL_TITLE)).toBeVisible();
    // Live API is unreachable → honest "Paper preview" source chip.
    await expect(page.getByTestId("search-source-mock")).toBeVisible();
    await expect(page.getByTestId("search-no-results")).toBeHidden();

    assertNoConsoleErrors(errors.filter((e) => !ENV_NOISE.test(e)), "palette typing");
  });

  test("arrow keys navigate and Enter opens the highlighted market", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    await openPaletteViaTriggerClick(page);
    const input = page.getByTestId("search-input");
    await input.pressSequentially("Lakers", { delay: 20 });
    await expect(page.getByTestId("search-result-item").first()).toBeVisible({
      timeout: 10_000,
    });

    // Down to the second row, up to the first — Enter opens the highlighted one.
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("Enter");

    await page.waitForURL(`**/markets/${CANONICAL_SLUG}`, {
      timeout: 45_000,
      waitUntil: "domcontentloaded",
    });
    expect(page.url()).toContain(`/markets/${CANONICAL_SLUG}`);

    assertNoConsoleErrors(errors.filter((e) => !ENV_NOISE.test(e)), "palette Enter navigation");
  });

  test("clicking a result navigates to its market page", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    // Force the paper-mock catalog (the seeded live DB has no Bitcoin market,
    // so the live path would honestly return zero rows).
    await page.route("**/api/v1/search**", (route) => route.abort());

    await openPaletteViaTriggerClick(page);
    const input = page.getByTestId("search-input");
    await input.pressSequentially("Bitcoin", { delay: 20 });

    const row = page.getByTestId("search-result-item").first();
    await expect(row).toBeVisible({ timeout: 10_000 });
    await expect(row).toContainText("Bitcoin");
    await row.click();

    await page.waitForURL("**/markets/btc-150k-2026-12-31", {
      timeout: 45_000,
      waitUntil: "domcontentloaded",
    });
    expect(page.url()).toContain("/markets/btc-150k-2026-12-31");

    assertNoConsoleErrors(errors.filter((e) => !ENV_NOISE.test(e)), "palette click navigation");
  });

  test("a query with no matches renders the no-results state", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    await openPaletteViaHotkey(page);
    const input = page.getByTestId("search-input");
    await input.pressSequentially("zzqq-not-a-market", { delay: 15 });

    await expect(page.getByTestId("search-no-results")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("search-result-item")).toHaveCount(0);

    assertNoConsoleErrors(errors.filter((e) => !ENV_NOISE.test(e)), "palette no-results");
  });
});
