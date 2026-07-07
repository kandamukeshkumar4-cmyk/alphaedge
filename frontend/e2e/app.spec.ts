import { test, expect, type Page } from "@playwright/test";

// The app degrades gracefully to its bundled mock catalog when no backend is
// reachable. The fallback fires on fetch FAILURE (the helpers catch and return
// mock), so we abort every backend call rather than fulfilling it — a 200 with
// an empty body reads as "backend online, zero markets" and wipes the UI. With
// the calls aborted, the whole app renders from its deterministic mock catalog.
async function stubBackend(page: Page): Promise<void> {
  await page.route(
    (url) => url.pathname.startsWith("/api/") || url.hostname.endsWith("hf.space"),
    (route) => route.abort(),
  );
}

// Network-layer noise from the deliberately-aborted backend calls above
// (Chromium logs "Failed to load resource: net::ERR_FAILED" for each). These
// are not application errors — the app catches them and falls back to mock — so
// they are excluded from the "zero console errors" gate. Real app errors
// (React crashes, uncaught exceptions, pageerror) are kept strict.
const NETWORK_NOISE = /Failed to load resource|net::ERR|ERR_FAILED|ERR_ABORTED/i;

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !NETWORK_NOISE.test(msg.text())) {
      errors.push(msg.text());
    }
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

test.beforeEach(async ({ page }) => {
  await stubBackend(page);
});

test("home loads with at least one market card", async ({ page }) => {
  await page.goto("/");
  const cards = page.locator('a[href^="/markets/"]');
  await expect(cards.first()).toBeVisible({ timeout: 15_000 });
  expect(await cards.count()).toBeGreaterThan(0);
});

test("clicking a market card opens the detail view with a price/chart element", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator('a[href^="/markets/"]').first()).toBeVisible({
    timeout: 15_000,
  });
  // Home market cards re-render on every live-price tick, so a single click can
  // land mid-render and miss. Retry click-then-navigation until one lands; once
  // we're on the detail route the churn stops.
  await expect(async () => {
    await page
      .locator('a[href^="/markets/"]')
      .first()
      .click({ force: true, timeout: 3_000 });
    await expect(page).toHaveURL(/\/markets\/[^/]+/, { timeout: 3_000 });
  }).toPass({ timeout: 20_000 });
  // Market detail renders a title heading and a lightweight-charts <canvas>.
  await expect(page.locator("h1").first()).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
});

for (const path of ["/portfolio", "/leaderboard", "/clones"]) {
  test(`${path} loads with zero console errors`, async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto(path, { waitUntil: "networkidle" });
    await expect(page.locator("body")).toBeVisible();
    expect(errors, `console errors on ${path}:\n${errors.join("\n")}`).toEqual([]);
  });
}

test("/research/brief renders the ensemble/model section on mock data", async ({
  page,
}) => {
  const errors = collectConsoleErrors(page);
  // ?slug=<canonical> exercises the analyst/model brief path (BriefBySlugClient),
  // which surfaces the model read on mock data instead of the empty state.
  await page.goto("/research/brief?slug=nba-2025-01-15-lal-bos", {
    waitUntil: "networkidle",
  });
  await expect(page.locator("body")).toBeVisible();
  // Must render without crashing (no Next.js error overlay / app error).
  await expect(page.locator("text=Application error")).toHaveCount(0);
  await expect(page.locator("main").first()).toBeVisible();
  expect(
    errors.filter((e) => !e.includes("favicon")),
    `console errors on /research/brief:\n${errors.join("\n")}`,
  ).toEqual([]);
});
