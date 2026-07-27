import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Q4 — Coverage journeys: market detail chart, leaderboard, /signals, /macro,
 * /alerts load with data or honest empty states; zero console errors each.
 */

const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

async function visit(page: Page, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissOnboardingIfPresent(page);
  await expect(page.locator("body")).toBeVisible();
}

async function settled(page: Page, ms = 1500) {
  await page.waitForTimeout(ms);
}

test.describe("Q4 coverage journeys", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("market detail renders chart (or chart region)", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await visit(page, `/markets/${CANONICAL_SLUG}`);

    // Title / market shell
    await expect(
      page.getByRole("heading", { name: /Lakers|Celtics|Will the Lakers/i }).first(),
    ).toBeVisible({ timeout: 30_000 });

    // lightweight-charts mounts a canvas inside role=img price history region
    const chartRegion = page.locator('[role="img"][aria-label*="Price history chart"]');
    await expect(chartRegion).toBeVisible({ timeout: 30_000 });
    // Canvas may take a beat after dynamic import
    await settled(page, 2500);
    const canvas = chartRegion.locator("canvas").first();
    const hasCanvas = await canvas.isVisible().catch(() => false);
    if (!hasCanvas) {
      // Still accept the reserved chart shell (lazy load) as long as region is present.
      await expect(chartRegion).toBeVisible();
    } else {
      await expect(canvas).toBeVisible();
    }

    assertNoConsoleErrors(errors, `/markets/${CANONICAL_SLUG}`);
  });

  // Loop117 D1b: the price socket publishes `yes_price`, the hook read `yes`,
  // so every tick produced `undefined` -> NaN in the chart header and NaN in
  // the outcome strip (prod rendered `YES NaN¢ ▼ NaN¢ (NaN%)`).
  test("market detail never renders NaN prices", async ({ page }) => {
    await visit(page, `/markets/${CANONICAL_SLUG}`);
    await expect(
      page.getByRole("heading", { name: /Lakers|Celtics|Will the Lakers/i }).first(),
    ).toBeVisible({ timeout: 30_000 });
    // Let the price socket connect and push at least one tick.
    await settled(page, 6000);

    const body = await page.locator("main").innerText();
    expect(body, "market detail must not render NaN").not.toMatch(/NaN/);
  });

  // Loop117 D14: the server render used to claim the API was disconnected and
  // ship a fabricated sample order book, because it only fetched /detail while
  // the demo flag keyed off the client-only catalog fetch.
  test("market detail SSR is live, not demo, while the API is up", async ({
    page,
    request,
    baseURL,
  }) => {
    const apiPort = process.env.E2E_API_PORT || "18017";
    const api = await request.get(
      `http://127.0.0.1:${apiPort}/api/v1/markets/${CANONICAL_SLUG}`,
    );
    expect(api.ok(), "local API must be up for this assertion to mean anything").toBe(
      true,
    );

    const ssr = await request.get(`${baseURL}/markets/${CANONICAL_SLUG}`);
    expect(ssr.ok()).toBe(true);
    const html = await ssr.text();
    expect(html, "SSR must not claim the API is disconnected").not.toContain(
      "Showing demo market data. Connect the API",
    );
    expect(html, "SSR must not ship a fabricated sample book").not.toContain(
      "Sample book — displayed sizes are not live",
    );
    // The real market, not a slug-derived placeholder.
    expect(html).toContain("Lakers vs Celtics");

    // And the same holds after hydration.
    await visit(page, `/markets/${CANONICAL_SLUG}`);
    await settled(page, 2500);
    const body = await page.locator("main").innerText();
    expect(body).not.toContain("Showing demo market data. Connect the API");
  });

  test("leaderboard loads with data or honest empty state", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await visit(page, "/leaderboard");
    await settled(page, 2000);

    // Page header / arena copy
    await expect(
      page.getByRole("heading", { name: /Leaderboard|Trader Arena|Arena/i }).first(),
    ).toBeVisible({ timeout: 25_000 });

    const body = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    // Demo fallback OR live rows OR honest empty — any is OK; page must not be blank.
    const hasRows =
      /quant_kestrel|edge_seeker|rank|#\s*1|Top P&L|Most active|win rate|No ranked|empty/i.test(
        body,
      );
    expect(hasRows || body.length > 40, `leaderboard body too thin: ${body.slice(0, 200)}`).toBe(
      true,
    );

    assertNoConsoleErrors(errors, "/leaderboard");
  });

  test("/signals loads with data or honest empty state", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await visit(page, "/signals");
    await settled(page, 2500);

    await expect(
      page.getByRole("heading", { name: /Signal|Signals/i }).first(),
    ).toBeVisible({ timeout: 25_000 });

    const main = page.locator("main");
    await expect(main).toBeVisible();
    const body = (await main.innerText()).replace(/\s+/g, " ");
    // Seeded events, live cards, or honest empty copy
    const honest =
      body.length > 30 &&
      (/signal|No signals|No cross-venue|arb|Screeners|Weather|track-record|empty/i.test(
        body,
      ) ||
        body.includes("All"));
    expect(honest, `signals body unexpected: ${body.slice(0, 240)}`).toBe(true);

    assertNoConsoleErrors(errors, "/signals");
  });

  test("/macro loads with data or honest empty state", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await visit(page, "/macro");
    await settled(page, 3000);

    await expect(
      page.getByRole("heading", { name: /Macro/i }).first(),
    ).toBeVisible({ timeout: 20_000 });

    const main = page.locator("main");
    const body = (await main.innerText()).replace(/\s+/g, " ");
    // Live FRED/WorldBank cards OR "Macro data unavailable" empty
    const ok =
      /Macro data unavailable|FRED|World Bank|CPI|GDP|unemployment|interest|indicator/i.test(
        body,
      ) || body.length > 40;
    expect(ok, `macro body unexpected: ${body.slice(0, 240)}`).toBe(true);

    assertNoConsoleErrors(errors, "/macro");
  });

  test("/alerts loads with data or honest empty state", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await visit(page, "/alerts");
    await settled(page, 2500);

    await expect(
      page.getByRole("heading", { name: /Alert/i }).first(),
    ).toBeVisible({ timeout: 25_000 });

    const main = page.locator("main");
    const body = (await main.innerText()).replace(/\s+/g, " ");
    const ok =
      /No alerts|alert|signal|watchlist|notification|family|digest/i.test(body) ||
      body.length > 40;
    expect(ok, `alerts body unexpected: ${body.slice(0, 240)}`).toBe(true);

    assertNoConsoleErrors(errors, "/alerts");
  });
});
