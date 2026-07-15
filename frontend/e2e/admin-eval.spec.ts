import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { CANONICAL_SLUG } from "./helpers/local-api";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * G3 — Admin + eval journeys (Loop V28).
 * Dev admin key via UI (not localStorage); stats render; pause/unpause
 * round-trip on nba-2025-01-15-lal-bos; /eval drift honest empty; zero
 * console errors on each new page.
 */

/** Matches start-local-stack.mjs ADMIN_API_KEY. Local stack only. */
const DEV_ADMIN_KEY = "dev-admin-key";

async function storageHasSecret(page: Page, secret: string): Promise<boolean> {
  return page.evaluate((needle) => {
    const haystacks: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k) haystacks.push(k, localStorage.getItem(k) ?? "");
    }
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k) haystacks.push(k, sessionStorage.getItem(k) ?? "");
    }
    return haystacks.some((v) => v.includes(needle));
  }, secret);
}

async function enterAdminKey(page: Page, key: string) {
  await page.goto("/admin", {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await dismissOnboardingIfPresent(page);
  await expect(
    page.getByRole("heading", { name: /Admin API Key/i }),
  ).toBeVisible({ timeout: 20_000 });
  await page.locator("#admin-api-key").fill(key);
  await page.getByRole("button", { name: /Save Key/i }).click();
  await expect(
    page.getByRole("button", { name: /Change API key/i }),
  ).toBeVisible({ timeout: 10_000 });
}

test.describe("G3 admin + eval journeys", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("admin key via UI not in storage; stats; pause/unpause; eval empty", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const errors = collectConsoleErrors(page);

    // ── Admin: enter dev key via UI ──
    await enterAdminKey(page, DEV_ADMIN_KEY);
    assertNoConsoleErrors(errors, "/admin after key");

    // Key must NOT land in localStorage or sessionStorage
    expect(
      await storageHasSecret(page, DEV_ADMIN_KEY),
      "admin key must not be persisted in localStorage/sessionStorage",
    ).toBe(false);
    // Also scan common storage keys for accidental persistence
    const storageSnapshot = await page.evaluate(() => {
      const out: Record<string, string | null> = {};
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k) out[`ls:${k}`] = localStorage.getItem(k);
      }
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i);
        if (k) out[`ss:${k}`] = sessionStorage.getItem(k);
      }
      return out;
    });
    for (const [k, v] of Object.entries(storageSnapshot)) {
      expect(v ?? "", `storage ${k}`).not.toContain(DEV_ADMIN_KEY);
    }

    // ── Stats render ──
    await expect(
      page.getByRole("heading", { name: /System stats/i }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/^Users$/i).first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(/^Open markets$/i).first()).toBeVisible();
    await expect(page.getByText(/^Trades · 24h$/i).first()).toBeVisible();
    // Numeric tiles (mono) present — at least one digit somewhere in stats
    const statsSection = page.locator("#stats");
    await expect(statsSection).toBeVisible();
    await expect(statsSection.locator("dd").first()).toBeVisible({
      timeout: 15_000,
    });
    const statsText = await statsSection.innerText();
    expect(statsText, "stats should include numeric values").toMatch(/\d/);

    // ── Pause / unpause round-trip on canonical market ──
    const markets = page.locator("#markets");
    await expect(
      markets.getByRole("heading", { name: /^Markets$/i }),
    ).toBeVisible({ timeout: 15_000 });

    const row = markets.locator("tr").filter({ hasText: CANONICAL_SLUG });
    await expect(row).toBeVisible({ timeout: 25_000 });
    await expect(row.getByText(/^open$/i)).toBeVisible();

    await row.getByRole("button", { name: /^Pause$/i }).click();
    await expect(row.getByText(/^locked$/i)).toBeVisible({ timeout: 20_000 });
    await expect(row.getByRole("button", { name: /^Unpause$/i })).toBeVisible();

    await row.getByRole("button", { name: /^Unpause$/i }).click();
    await expect(row.getByText(/^open$/i)).toBeVisible({ timeout: 20_000 });
    await expect(row.getByRole("button", { name: /^Pause$/i })).toBeVisible();

    assertNoConsoleErrors(errors, "/admin pause-unpause");

    // Re-check storage after mutations
    expect(await storageHasSecret(page, DEV_ADMIN_KEY)).toBe(false);

    // ── /eval: drift panel honest empty (or data if present) ──
    await page.goto("/eval", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(
      page.getByRole("heading", { name: /Proof dashboard/i }),
    ).toBeVisible({ timeout: 20_000 });

    const drift = page.getByTestId("drift-series-panel");
    await expect(drift).toBeVisible({ timeout: 20_000 });
    await expect(
      drift.getByRole("heading", { name: /Calibration drift history/i }),
    ).toBeVisible();

    // Honest empty is the expected local-stack state; data path is also OK.
    const emptyOrData = drift.getByText(
      /No drift snapshots yet|Drift data is unavailable|Latest Brier|Latest snapshot/i,
    );
    await expect(emptyOrData.first()).toBeVisible({ timeout: 20_000 });

    // Ensemble section should not fabricate measured bars without data
    const ensemble = page.getByTestId("ensemble-autolab-section");
    await expect(ensemble).toBeVisible();
    // Local stack typically lands in not_run / insufficient_data
    const honest = page.getByTestId("ensemble-not-measured");
    const measured = page.getByTestId("ensemble-measured");
    const honestVisible = await honest.isVisible().catch(() => false);
    const measuredVisible = await measured.isVisible().catch(() => false);
    expect(
      honestVisible || measuredVisible,
      "ensemble section must settle to honest empty or real measurement",
    ).toBe(true);
    if (honestVisible) {
      await expect(honest.getByText(/Not yet measured|Insufficient data/i)).toBeVisible();
    }

    await page.waitForTimeout(800);
    assertNoConsoleErrors(errors, "/eval");
  });
});
