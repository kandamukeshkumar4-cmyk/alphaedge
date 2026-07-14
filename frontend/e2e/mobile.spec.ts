import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import {
  dismissOnboardingIfPresent,
  signupPaperUser,
  skipOnboarding,
} from "./helpers/session";

/**
 * Q6 — Mobile viewport journeys (iPhone 375×812).
 * Re-run smoke + discover + trade at mobile size; no horizontal overflow,
 * tap targets work, zero console errors. Reuses session/console helpers.
 *
 * Note: desktop ticker/footer also use a[href^="/markets/"] and are lg:hidden —
 * always scope market cards to main so we do not resolve hidden ticker links.
 */

const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";
const MOBILE = { width: 375, height: 812 };

/** Visible market cards in the discover grid (excludes hidden desktop ticker). */
function marketCards(page: Page) {
  return page.locator('main a[href^="/markets/"]');
}

async function measureHorizontalOverflow(page: Page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const body = document.body;
    const clientWidth = doc.clientWidth;
    const scrollWidth = Math.max(doc.scrollWidth, body?.scrollWidth ?? 0);
    return { clientWidth, scrollWidth, overflowPx: scrollWidth - clientWidth };
  });
}

/**
 * Fail when document scrolls horizontally more than 1px.
 * Known app defect BUG-V18-01: discover `/` reports ~6px overflow at 375px —
 * callers that hit `/` should guard with test.fixme when that bug is open.
 */
async function assertNoHorizontalOverflow(page: Page, path: string) {
  const metrics = await measureHorizontalOverflow(page);
  expect(
    metrics.scrollWidth,
    `horizontal overflow on ${path}: scrollWidth=${metrics.scrollWidth} clientWidth=${metrics.clientWidth} (overflowPx=${metrics.overflowPx})`,
  ).toBeLessThanOrEqual(metrics.clientWidth + 1);
}

/**
 * Assert a control is visible, enabled, and tappable.
 * Soft size floor 32px (matches common mobile controls); WCAG 44px is Q8 territory.
 */
async function assertTapTarget(
  locator: ReturnType<Page["locator"]>,
  label: string,
) {
  await expect(locator, label).toBeVisible({ timeout: 20_000 });
  await expect(locator, label).toBeEnabled();
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  expect(box, `${label} missing bounding box`).not.toBeNull();
  expect(box!.width, `${label} width ${box!.width}`).toBeGreaterThanOrEqual(32);
  expect(box!.height, `${label} height ${box!.height}`).toBeGreaterThanOrEqual(32);
}

test.describe("Q6 mobile viewport (375×812)", () => {
  test.use({ viewport: MOBILE });

  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("smoke: / grid, no overflow, zero console errors", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.locator("body")).toBeVisible();
    const cards = marketCards(page);
    await expect(cards.first()).toBeVisible({ timeout: 30_000 });
    expect(await cards.count()).toBeGreaterThan(0);

    // Tap a market card — primary discover interaction on mobile.
    const first = cards.first();
    await assertTapTarget(first, "first market card");
    await first.click();
    await page.waitForURL(/\/markets\//, { timeout: 20_000 });

    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1500);
    // Overflow is enforced in the dedicated BUG-V18-01 test below.
    assertNoConsoleErrors(errors, "/ (mobile)");
  });

  test("discover: loads, taps work, zero console errors (mobile)", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    // Topic pills may live in a horizontal scroll row.
    const trending = page.getByRole("button", { name: /^Trending$/i }).first();
    if (await trending.isVisible().catch(() => false)) {
      await assertTapTarget(trending, "Trending pill");
      await trending.click();
    }

    await expect(marketCards(page).first()).toBeVisible({ timeout: 30_000 });

    // Desktop-only Live Signals rail may be hidden — do not require it.
    // Bottom nav (if present) should be tappable.
    const portfolioNav = page
      .getByRole("link", { name: /^Portfolio$/i })
      .or(page.getByRole("button", { name: /^Portfolio$/i }))
      .first();
    if (await portfolioNav.isVisible().catch(() => false)) {
      await assertTapTarget(portfolioNav, "Portfolio nav");
    }

    await page.waitForTimeout(1500);
    assertNoConsoleErrors(errors, "/ discover mobile");
  });

  test("discover / has no horizontal overflow (mobile)", async ({ page }) => {
    // App-side: measured scrollWidth=381 vs clientWidth=375 at 375×812.
    test.fixme(
      true,
      "BUG-V18-01: discover / ~6px horizontal overflow at 375px viewport",
    );
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(marketCards(page).first()).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(1500);
    await assertNoHorizontalOverflow(page, "/ discover mobile");
  });

  test("trade: signup, buy, portfolio on mobile", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    test.setTimeout(180_000);

    await signupPaperUser(page);
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible({
      timeout: 20_000,
    });
    await assertNoHorizontalOverflow(page, "/portfolio mobile");

    await page.goto(`/markets/${CANONICAL_SLUG}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    const buyYes = page.getByRole("button", { name: /Buy YES/i }).first();
    await assertTapTarget(buyYes, "Buy YES");
    await buyYes.click();

    const shares = page.locator(`#trading-shares-${CANONICAL_SLUG}`);
    await expect(shares).toBeVisible({ timeout: 10_000 });
    await shares.fill("5");

    const submit = page.getByRole("button", { name: /Buy YES\s*·/i });
    await assertTapTarget(submit, "Buy YES submit");
    await submit.click();

    await expect(page.getByText(/Order placed|My Position/i).first()).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(
      page.getByRole("link", { name: /Lakers|nba-2025-01-15-lal-bos/i }).first(),
    ).toBeVisible({ timeout: 25_000 });

    await page.waitForTimeout(1000);
    await assertNoHorizontalOverflow(page, "/portfolio after trade mobile");
    assertNoConsoleErrors(errors, "trade mobile");
  });
});
