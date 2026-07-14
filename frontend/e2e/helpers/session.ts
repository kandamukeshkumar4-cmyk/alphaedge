import type { Page } from "@playwright/test";

/**
 * Shared Playwright session helpers for Loop V17 journeys.
 * Local stack only — never talks to prod.
 */

/** Suppress first-visit onboarding modal so journeys can click through UI. */
export async function skipOnboarding(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("alphaedge.onboarded", "true");
    } catch {
      /* ignore */
    }
  });
}

/** Dismiss onboarding if it still appears (e.g. storage blocked). */
export async function dismissOnboardingIfPresent(page: Page): Promise<void> {
  const skip = page.getByRole("button", { name: /^Skip$/i }).first();
  if (await skip.isVisible({ timeout: 1500 }).catch(() => false)) {
    await skip.click();
  }
}

export function uniqueEmail(prefix = "loop17"): string {
  return `${prefix}+${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** Sign up a fresh paper user via the UI; lands on /portfolio. */
export async function signupPaperUser(
  page: Page,
  opts?: { email?: string; password?: string },
): Promise<{ email: string; password: string }> {
  const email = opts?.email ?? uniqueEmail();
  const password = opts?.password ?? "Loop17qa!";

  await page.goto("/auth/signup", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);

  await page.locator("#signup-email").fill(email);
  await page.locator("#signup-password").fill(password);
  await page.locator("#signup-confirm").fill(password);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /Create account/i }).click();

  await page.waitForURL(/\/portfolio/, { timeout: 30_000 });
  return { email, password };
}

/** Log in an existing paper user via the UI; lands on /portfolio. */
export async function loginPaperUser(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/auth/login", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.getByRole("button", { name: /^Log in$/i }).click();
  await page.waitForURL(/\/portfolio/, { timeout: 30_000 });
}
