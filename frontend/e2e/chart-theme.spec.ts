import { test, expect } from "@playwright/test";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop30 P3 — chart chrome tokens flip under html.light.
 * Asserts computed --chart-text / --chart-grid differ dark vs light on the
 * market page (DOM evidence; not a visual screenshot gate).
 */

const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

test.describe("P3 chart theme tokens", () => {
  test("html.light flips --chart-text and --chart-grid on market page", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await skipOnboarding(page);
    await page.goto(`/markets/${CANONICAL_SLUG}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(
      page.getByRole("img", { name: /Price history chart/i }),
    ).toBeVisible({ timeout: 30_000 });

    const dark = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      return {
        text: s.getPropertyValue("--chart-text").trim(),
        grid: s.getPropertyValue("--chart-grid").trim(),
        hasLight: document.documentElement.classList.contains("light"),
      };
    });
    expect(dark.hasLight).toBe(false);
    expect(dark.text).toMatch(/143/);
    expect(dark.grid).toMatch(/28/);

    await page.evaluate(() => {
      document.documentElement.classList.add("light");
    });

    const light = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      return {
        text: s.getPropertyValue("--chart-text").trim(),
        grid: s.getPropertyValue("--chart-grid").trim(),
        hasLight: document.documentElement.classList.contains("light"),
      };
    });
    expect(light.hasLight).toBe(true);
    expect(light.text).toMatch(/55/);
    expect(light.grid).toMatch(/200/);
    expect(light.text).not.toBe(dark.text);
    expect(light.grid).not.toBe(dark.grid);
  });
});
