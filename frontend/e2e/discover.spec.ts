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

function parseCardCents(text: string): number | null {
  // Market cards render e.g. "55" + "¢" or "55¢"
  const m = text.match(/(\d{1,3})\s*¢/);
  if (!m) return null;
  return Number(m[1]);
}

test.describe("Q2 discover freshness", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("trending contains no decided markets (≤1¢ / ≥99¢)", async ({ page }) => {
    // V16 V1 not merged into loop17 base (loop16/freshness is parallel). Keep
    // the assertion in-suite as expected-fail until merge.
    test.fixme(true, "pending V16 merge — V1 trending excludes decided (≤1¢/≥99¢)");

    await openDiscoverTrending(page);
    const priceNodes = page.locator("main").locator("text=/\\d+\\s*¢/");
    const count = await priceNodes.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      const text = (await priceNodes.nth(i).innerText()).replace(/\s+/g, " ");
      const cents = parseCardCents(text);
      if (cents == null) continue;
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
    test.fixme(
      true,
      "pending V16 merge — signal rail should show market title, not bare delta:price_jump —",
    );

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
    test.fixme(
      true,
      "pending V16 merge — live ticker items must be unique market labels",
    );

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
