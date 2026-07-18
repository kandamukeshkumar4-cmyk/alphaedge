import type { Page } from "@playwright/test";

/**
 * Shared Playwright session helpers for Loop V17 journeys.
 * Local stack only — never talks to prod.
 */

/** Coach-marks localStorage key — keep in sync with CoachMarks.tsx. */
export const COACHMARKS_SEEN_KEY = "alphaedge.coachmarks.v1";

/**
 * Suppress first-visit onboarding modal + coach-marks card so journeys can
 * click through UI. Loop V72 (C2): seed coach-marks "seen" for every journey
 * that calls this helper; the dedicated coachmarks.spec.ts opts out.
 */
export async function skipOnboarding(page: Page): Promise<void> {
  await page.addInitScript((coachKey: string) => {
    try {
      localStorage.setItem("alphaedge.onboarded", "true");
      localStorage.setItem(coachKey, "true");
    } catch {
      /* ignore */
    }
  }, COACHMARKS_SEEN_KEY);
}

/** Pre-seed coach-marks "seen" without touching onboarding (visreg / extras). */
export async function skipCoachMarks(page: Page): Promise<void> {
  await page.addInitScript((coachKey: string) => {
    try {
      localStorage.setItem(coachKey, "true");
    } catch {
      /* ignore */
    }
  }, COACHMARKS_SEEN_KEY);
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

/** Fill a controlled React input so state updates (fill alone can race hydration). */
async function fillControlled(page: Page, selector: string, value: string): Promise<void> {
  const input = page.locator(selector);
  await input.waitFor({ state: "visible", timeout: 20_000 });
  await input.click();
  await input.fill("");
  await input.pressSequentially(value, { delay: 15 });
  await page.waitForFunction(
    ({ sel, expected }) => {
      const el = document.querySelector(sel) as HTMLInputElement | null;
      return el != null && el.value === expected;
    },
    { sel: selector, expected: value },
    { timeout: 10_000 },
  );
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
  await page.getByRole("heading", { name: /Join AlphaEdge/i }).waitFor({
    state: "visible",
    timeout: 20_000,
  });

  await fillControlled(page, "#signup-email", email);
  await fillControlled(page, "#signup-password", password);
  await fillControlled(page, "#signup-confirm", password);

  const agree = page.locator('input[type="checkbox"]');
  await agree.check({ force: true });
  // Ensure React controlled `agree` flipped (canSubmit requires it).
  await page.waitForFunction(() => {
    const box = document.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement | null;
    return box != null && box.checked;
  });

  const submit = page.getByRole("button", { name: /Create account/i });
  await expectEnabled(submit, 15_000);
  await submit.click();

  await page.waitForURL(/\/portfolio/, { timeout: 45_000 });
  return { email, password };
}

async function expectEnabled(
  locator: ReturnType<Page["getByRole"]>,
  timeoutMs: number,
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await locator.isEnabled()) return;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("Create account stayed disabled — form fields not accepted");
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
  await fillControlled(page, "#login-email", email);
  await fillControlled(page, "#login-password", password);
  // Prefer form submit — header also has a "Log in" button.
  await page.locator('main button[type="submit"]').click();
  await page.waitForURL(/\/portfolio/, { timeout: 45_000 });
}
