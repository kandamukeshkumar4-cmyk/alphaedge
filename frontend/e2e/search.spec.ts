import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { skipOnboarding } from "./helpers/session";

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

async function openPaletteViaHotkey(page: import("@playwright/test").Page) {
  await page.keyboard.press("ControlOrMeta+KeyK");
  await expect(page.getByTestId("search-palette")).toBeVisible();
}

test.describe("V91 search palette", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
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

    assertNoConsoleErrors(errors, "palette open/close");
  });

  test("typing shows paper mock results after the debounce", async ({ page }) => {
    const errors = collectConsoleErrors(page);

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

    assertNoConsoleErrors(errors, "palette typing");
  });

  test("arrow keys navigate and Enter opens the highlighted market", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    await page.getByTestId("search-trigger").click();
    await expect(page.getByTestId("search-palette")).toBeVisible();
    const input = page.getByTestId("search-input");
    await input.pressSequentially("Lakers", { delay: 20 });
    await expect(page.getByTestId("search-result-item").first()).toBeVisible({
      timeout: 10_000,
    });

    // Down to the second row, up to the first — Enter opens the highlighted one.
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("Enter");

    await page.waitForURL(`**/markets/${CANONICAL_SLUG}`, { timeout: 30_000 });
    expect(page.url()).toContain(`/markets/${CANONICAL_SLUG}`);

    assertNoConsoleErrors(errors, "palette Enter navigation");
  });

  test("clicking a result navigates to its market page", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    await page.getByTestId("search-trigger").click();
    const input = page.getByTestId("search-input");
    await input.pressSequentially("Bitcoin", { delay: 20 });

    const row = page.getByTestId("search-result-item").first();
    await expect(row).toBeVisible({ timeout: 10_000 });
    await expect(row).toContainText("Bitcoin");
    await row.click();

    await page.waitForURL("**/markets/btc-150k-2026-12-31", { timeout: 30_000 });
    expect(page.url()).toContain("/markets/btc-150k-2026-12-31");

    assertNoConsoleErrors(errors, "palette click navigation");
  });

  test("a query with no matches renders the no-results state", async ({ page }) => {
    const errors = collectConsoleErrors(page);

    await openPaletteViaHotkey(page);
    const input = page.getByTestId("search-input");
    await input.pressSequentially("zzqq-not-a-market", { delay: 15 });

    await expect(page.getByTestId("search-no-results")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("search-result-item")).toHaveCount(0);

    assertNoConsoleErrors(errors, "palette no-results");
  });
});
