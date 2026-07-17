/**
 * Loop V44 — visual regression baselines.
 *
 * Routes: /, market detail, /portfolio (empty), /leaderboard, /eval,
 * /admin/observability — both themes × desktop + 375px.
 *
 * Runs only under the Playwright `visreg` project (local). CI keeps
 * `--project=chromium` and never loads these shots (S3).
 */
import { test, expect, type Page } from "@playwright/test";
import { CANONICAL_SLUG } from "./helpers/local-api";
import {
  dismissOnboardingIfPresent,
  signupPaperUser,
  skipOnboarding,
} from "./helpers/session";
import {
  DESKTOP_VIEWPORT,
  MOBILE_VIEWPORT,
  prepareStableShot,
  SHOT_OPTIONS,
  type ThemeName,
} from "./helpers/stable-shot";

const DEV_ADMIN_KEY = "dev-admin-key";

const THEMES: ThemeName[] = ["dark", "light"];
const VIEWPORTS = [
  { name: "desktop", size: DESKTOP_VIEWPORT },
  { name: "mobile375", size: MOBILE_VIEWPORT },
] as const;

async function readyHome(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissOnboardingIfPresent(page);
  await expect(page.locator('main a[href^="/markets/"]').first()).toBeVisible({
    timeout: 30_000,
  });
}

async function readyMarket(page: Page) {
  await page.goto(`/markets/${CANONICAL_SLUG}`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
  await expect(
    page.getByRole("heading", { name: /Lakers|Celtics|Will the Lakers/i }).first(),
  ).toBeVisible({ timeout: 30_000 });
}

async function readyPortfolioEmpty(page: Page) {
  await signupPaperUser(page, {
    email: `visreg+${Date.now()}_${Math.floor(Math.random() * 1e6)}@example.com`,
  });
  await expect(page.getByText(/No paper trades yet/i)).toBeVisible({
    timeout: 20_000,
  });
}

async function readyLeaderboard(page: Page) {
  await page.goto("/leaderboard", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
  await expect(
    page.getByRole("heading", { name: /Leaderboard|Trader Arena|Arena/i }).first(),
  ).toBeVisible({ timeout: 25_000 });
}

async function readyEval(page: Page) {
  await page.goto("/eval", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
  await expect(
    page.getByRole("heading", { name: /Proof dashboard/i }),
  ).toBeVisible({ timeout: 20_000 });
}

async function readyObservability(page: Page) {
  // Full goto remounts admin layout (in-memory key lost) — enter key on
  // the observability URL so the prompt + boards share one mount.
  await page.goto("/admin/observability", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
  const keyHeading = page.getByRole("heading", { name: /Admin API Key/i });
  if (await keyHeading.isVisible({ timeout: 5_000 }).catch(() => false)) {
    // Controlled React input: fill can race hydration (DOM value set, but
    // draftKey still "" → Save stays disabled). Retry until Save enables.
    // Mirrors admin-eval enterAdminKey + session fillControlled.
    const input = page.locator("#admin-api-key");
    await input.waitFor({ state: "visible", timeout: 15_000 });
    const save = page.getByRole("button", { name: /Save Key/i });
    for (let attempt = 0; attempt < 3; attempt++) {
      await input.click();
      await input.fill("");
      await input.pressSequentially(DEV_ADMIN_KEY, { delay: 15 });
      await page.waitForFunction(
        ({ sel, expected }) => {
          const el = document.querySelector(sel) as HTMLInputElement | null;
          return el != null && el.value === expected;
        },
        { sel: "#admin-api-key", expected: DEV_ADMIN_KEY },
        { timeout: 10_000 },
      );
      if (await save.isEnabled().catch(() => false)) break;
      await page.waitForTimeout(250);
    }
    await expect(save).toBeEnabled({ timeout: 10_000 });
    await save.click();
    await expect(
      page.getByRole("button", { name: /Change API key/i }),
    ).toBeVisible({ timeout: 10_000 });
  }
  await expect(
    page.getByRole("heading", { name: /System Observability/i }),
  ).toBeVisible({ timeout: 20_000 });
}

const SURFACES: Array<{
  id: string;
  ready: (page: Page) => Promise<void>;
  /** Fresh signup mutates auth — only once per viewport group. */
  needsAuth?: boolean;
}> = [
  { id: "home", ready: readyHome },
  { id: "market", ready: readyMarket },
  { id: "portfolio-empty", ready: readyPortfolioEmpty, needsAuth: true },
  { id: "leaderboard", ready: readyLeaderboard },
  { id: "eval", ready: readyEval },
  { id: "admin-observability", ready: readyObservability },
];

test.describe("V44 visual regression", () => {
  test.describe.configure({ mode: "serial" });

  for (const vp of VIEWPORTS) {
    for (const theme of THEMES) {
      test.describe(`${vp.name} / ${theme}`, () => {
        test.use({ viewport: vp.size });

        test.beforeEach(async ({ page }) => {
          await skipOnboarding(page);
        });

        for (const surface of SURFACES) {
          test(`${surface.id}`, async ({ page }) => {
            test.setTimeout(180_000);
            await surface.ready(page);
            const mask = await prepareStableShot(page, theme);
            await expect(page).toHaveScreenshot(
              `${surface.id}-${theme}-${vp.name}.png`,
              { ...SHOT_OPTIONS, mask },
            );
          });
        }
      });
    }
  }
});
