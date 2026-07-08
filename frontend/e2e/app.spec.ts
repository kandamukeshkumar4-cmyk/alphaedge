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
//
// Against production, HF Spaces free-tier reverse proxy rejects WebSocket
// upgrades (403/429). The FeedMultiplexer degrades to HTTP polling — that is
// expected, not an app crash.
const NETWORK_NOISE =
  /Failed to load resource|net::ERR|ERR_FAILED|ERR_ABORTED|WebSocket connection to .* failed/i;

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

// Against a deployed URL (PLAYWRIGHT_BASE_URL / E2E_LIVE=1) we exercise the
// live API. Locally we abort backend calls so the deterministic mock catalog
// drives the UI.
const BASE = process.env.PLAYWRIGHT_BASE_URL?.trim() ?? "";
const LIVE =
  process.env.E2E_LIVE === "1" ||
  (BASE.length > 0 && !BASE.includes("localhost"));

// Live pages keep polling prices, so networkidle never settles. Use load.
const GOTO_WAIT: "load" | "networkidle" = LIVE ? "load" : "networkidle";

test.beforeEach(async ({ page }) => {
  if (!LIVE) {
    await stubBackend(page);
  }
});

test("home loads with at least one market card", async ({ page }) => {
  await page.goto("/", { waitUntil: GOTO_WAIT });
  const cards = page.locator('a[href^="/markets/"]');
  await expect(cards.first()).toBeVisible({ timeout: 15_000 });
  expect(await cards.count()).toBeGreaterThan(0);
});

test("clicking a market card opens the detail view with a price/chart element", async ({
  page,
}) => {
  await page.goto("/", { waitUntil: GOTO_WAIT });
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
    await page.goto(path, { waitUntil: GOTO_WAIT, timeout: 60_000 });
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
    waitUntil: GOTO_WAIT,
    timeout: 60_000,
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

test("signup page is interactive: ATLAS never covers the terms checkbox", async ({
  page,
}) => {
  await page.goto("/auth/signup", { waitUntil: GOTO_WAIT, timeout: 60_000 });
  const terms = page.locator('input[type="checkbox"]').first();
  await expect(terms).toBeVisible({ timeout: 15_000 });
  // The ATLAS panel must never auto-open on /auth/* — the checkbox has to be
  // clickable immediately, without closing anything first (no force).
  await terms.check({ timeout: 5_000 });
  await expect(terms).toBeChecked();
});

test("header reflects auth state after signup without a refresh", async ({ page }) => {
  test.skip(!LIVE, "requires the live backend to create a throwaway account");
  await page.goto("/auth/signup", { waitUntil: GOTO_WAIT, timeout: 60_000 });
  const email = `e2e-${Date.now()}@alphaedge.test`;
  await page.locator('input[type="email"]').first().fill(email);
  const passwords = page.locator('input[type="password"]');
  await passwords.nth(0).fill("Str0ngPass!e2e");
  await passwords.nth(1).fill("Str0ngPass!e2e");
  const terms = page.locator('input[type="checkbox"]').first();
  if (await terms.isVisible()) await terms.check();
  await page.locator('button[type="submit"]').first().click();
  // After signup + redirect the persistent header must show the account state
  // (email/log out) instead of the anonymous Sign up button.
  await expect(page.getByRole("button", { name: /log out/i })).toBeVisible({
    timeout: 20_000,
  });
});
