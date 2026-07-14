import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { skipOnboarding, dismissOnboardingIfPresent } from "./helpers/session";

/**
 * Q2 — Discover freshness journey (asserts Loop V16 V1 behavior).
 *
 * If V16 fixes are not in this base, mark specific assertions test.fixme with
 * reference "pending V16 merge" — do not fail the suite.
 */

async function openDiscoverTrending(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissOnboardingIfPresent(page);
  // Default topic is trending (no ?topic=). Ensure the pill is active.
  const trending = page.getByRole("button", { name: /^Trending$/i }).first();
  if (await trending.isVisible().catch(() => false)) {
    await trending.click();
  }
  await expect(page.locator('a[href^="/markets/"]').first()).toBeVisible({
    timeout: 30_000,
  });
}

test.describe("Q2 discover freshness", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("trending contains no decided markets (≤1¢ / ≥99¢)", async ({ page }) => {
    // V16 V1 is merged (89d1297) — guard is live.
    await openDiscoverTrending(page);
    // Prices render as "42" + nested "¢" span — prefer main text scan over
    // fragile text=/regex/ leaf locators (flaked with count=0 while DOM had ¢).
    const pricePara = page.locator("main p.font-mono").filter({ hasText: /¢/ });
    await expect(pricePara.first()).toBeVisible({ timeout: 20_000 });

    const mainText = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    const matches = [...mainText.matchAll(/(\d{1,3})\s*¢/g)];
    expect(matches.length, `no ¢ prices in main: ${mainText.slice(0, 200)}`).toBeGreaterThan(
      0,
    );
    for (const m of matches) {
      const cents = Number(m[1]);
      expect(
        cents,
        `decided market price ${cents}¢ found in trending grid`,
      ).toBeGreaterThan(1);
      expect(
        cents,
        `decided market price ${cents}¢ found in trending grid`,
      ).toBeLessThan(99);
    }
  });

  test("signals rail rows include market names (not bare delta:price_jump —)", async ({
    page,
  }) => {
    // V16 V2 is merged (89d1297) — guard is live.
    await openDiscoverTrending(page);
    // Left rail "Live Signals" section (desktop). Viewport is Desktop Chrome.
    const signalsHeader = page.getByRole("heading", { name: /Live Signals/i });
    await expect(signalsHeader).toBeVisible({ timeout: 20_000 });
    const section = signalsHeader.locator("xpath=ancestor::section[1]");
    const body = (await section.innerText()).replace(/\s+/g, " ").trim();
    expect(body.length).toBeGreaterThan(0);
    // Bare signal-type rows with em-dash placeholders are the V16 defect.
    expect(body).not.toMatch(/delta:\s*price_jump\s*[—-]\s*$/i);
    expect(body).not.toMatch(/delta:price_jump\s*[—-]/i);
    // Prefer market names over raw signal_type labels.
    expect(body).not.toMatch(/\bdelta:price jump\b/i);
  });

  test("ticker items are unique", async ({ page }) => {
    // V16 V3 is merged (89d1297) — guard is live.
    await openDiscoverTrending(page);
    // Footer ticker is desktop-only (lg:block). Wait briefly for fetch.
    await page.waitForTimeout(2000);
    const ticker = page.locator("text=● Live").first();
    const visible = await ticker.isVisible().catch(() => false);
    if (!visible) {
      // Honest empty ticker is OK when no signal events — uniqueness is vacuous.
      return;
    }
    const labels = page.locator(
      'div:has-text("● Live") a span.font-medium, div:has-text("● Live") span.font-medium',
    );
    const texts: string[] = [];
    const n = await labels.count();
    for (let i = 0; i < n; i++) {
      const t = (await labels.nth(i).innerText()).trim();
      if (t) texts.push(t);
    }
    // Marquee duplicates the list once for seamless loop — unique half only.
    const half = texts.slice(0, Math.ceil(texts.length / 2));
    const unique = new Set(half);
    expect(unique.size, `duplicate ticker labels: ${half.join(" | ")}`).toBe(
      half.length,
    );
  });

  test("discover page loads with zero console errors (always enforced)", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await openDiscoverTrending(page);
    await page.waitForTimeout(1500);
    assertNoConsoleErrors(errors, "/");
  });
});
