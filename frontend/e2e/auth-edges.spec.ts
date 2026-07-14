import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import {
  dismissOnboardingIfPresent,
  signupPaperUser,
  skipOnboarding,
  uniqueEmail,
} from "./helpers/session";

/**
 * Q7 — Auth edge journeys.
 * Wrong password, duplicate signup, invalid token mid-session, protected-route
 * redirect. Honest error states; never a blank/crashed page.
 */

async function assertNotCrashed(page: Page, label: string) {
  await expect(page.locator("body"), label).toBeVisible();
  // Next/React fatal overlays
  await expect(
    page.getByText(/Application error|Unhandled Runtime Error|This page couldn't load/i),
  ).toHaveCount(0);
  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ").trim();
  expect(text.length, `${label}: blank body`).toBeGreaterThan(20);
}

/** Fill controlled React inputs the same way session helpers do. */
async function fillField(page: Page, selector: string, value: string) {
  const input = page.locator(selector);
  await input.waitFor({ state: "visible", timeout: 20_000 });
  await input.click();
  await input.fill("");
  await input.pressSequentially(value, { delay: 12 });
}

test.describe("Q7 auth edge journeys", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("wrong password shows honest error, stays on login", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    const { email } = await signupPaperUser(page);

    // Clear session so login form is used (not already-authed redirect).
    await page.evaluate(() => {
      localStorage.removeItem("alphaedge.accessToken");
      localStorage.removeItem("alphaedge.userEmail");
    });

    await page.goto("/auth/login", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByRole("heading", { name: /Welcome back/i })).toBeVisible({
      timeout: 20_000,
    });

    await fillField(page, "#login-email", email);
    await fillField(page, "#login-password", "DefinitelyWrongPass1!");
    await page.locator('main button[type="submit"]').click();

    // Error toast (role=alert) — title or body
    const alert = page.getByRole("alert").filter({
      hasText: /Login failed|Invalid email or password|incorrect|credentials/i,
    });
    await expect(alert.first()).toBeVisible({ timeout: 15_000 });

    // Still on login — not a silent redirect or crash
    await expect(page).toHaveURL(/\/auth\/login/);
    await expect(page.getByRole("heading", { name: /Welcome back/i })).toBeVisible();
    await assertNotCrashed(page, "wrong password");
    assertNoConsoleErrors(errors, "wrong password");
  });

  test("duplicate signup shows honest error, stays on signup", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    const email = uniqueEmail("loop18-dup");
    const password = "Loop18qa!";

    // First account succeeds
    await signupPaperUser(page, { email, password });
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible({
      timeout: 20_000,
    });

    // Clear session and attempt same email again
    await page.evaluate(() => {
      localStorage.removeItem("alphaedge.accessToken");
      localStorage.removeItem("alphaedge.userEmail");
    });

    await page.goto("/auth/signup", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByRole("heading", { name: /Join AlphaEdge/i })).toBeVisible({
      timeout: 20_000,
    });

    await fillField(page, "#signup-email", email);
    await fillField(page, "#signup-password", password);
    await fillField(page, "#signup-confirm", password);
    const agree = page.locator('input[type="checkbox"]');
    await agree.check({ force: true });
    await page.waitForFunction(() => {
      const box = document.querySelector(
        'input[type="checkbox"]',
      ) as HTMLInputElement | null;
      return box != null && box.checked;
    });

    const submit = page.getByRole("button", { name: /Create account/i });
    await expect(submit).toBeEnabled({ timeout: 15_000 });
    await submit.click();

    const alert = page.getByRole("alert").filter({
      hasText: /Signup failed|already|exists|registered|duplicate|email/i,
    });
    await expect(alert.first()).toBeVisible({ timeout: 20_000 });

    await expect(page).toHaveURL(/\/auth\/signup/);
    await expect(page.getByRole("heading", { name: /Join AlphaEdge/i })).toBeVisible();
    await assertNotCrashed(page, "duplicate signup");
    assertNoConsoleErrors(errors, "duplicate signup");
  });

  test("invalid token mid-session yields honest state, not crash", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await signupPaperUser(page);
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible({
      timeout: 20_000,
    });

    // Corrupt the bearer token while keeping a non-empty session key
    await page.evaluate(() => {
      localStorage.setItem("alphaedge.accessToken", "not.a.valid.jwt.token");
    });

    await page.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    // Honest outcomes: redirect to login OR stay with an error / empty auth message.
    // Never a blank crash shell.
    await page.waitForTimeout(2500);
    const url = page.url();
    const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");

    const redirectedToLogin = /\/auth\/login/i.test(url);
    const honestError =
      /Log in|login|Failed to load|Unauthorized|401|invalid|expired|session|paper portfolio/i.test(
        body,
      );

    expect(
      redirectedToLogin || honestError,
      `expected login redirect or honest error; url=${url} body=${body.slice(0, 240)}`,
    ).toBe(true);
    await assertNotCrashed(page, "invalid token");
    assertNoConsoleErrors(errors, "invalid token");
  });

  test("protected /portfolio redirects unauthenticated users to login", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);

    // Ensure no leftover session from other tests / reuseExistingServer.
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.evaluate(() => {
      localStorage.removeItem("alphaedge.accessToken");
      localStorage.removeItem("alphaedge.userEmail");
    });

    await page.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    await expect(page).toHaveURL(/\/auth\/login/, { timeout: 20_000 });
    await expect(page.getByRole("heading", { name: /Welcome back/i })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.locator("#login-email")).toBeVisible();
    await assertNotCrashed(page, "protected redirect");
    assertNoConsoleErrors(errors, "protected redirect");
  });
});
