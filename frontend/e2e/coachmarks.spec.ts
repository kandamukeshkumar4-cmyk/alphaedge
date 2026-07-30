import { test, expect } from "@playwright/test";
import {
  COACHMARKS_SEEN_KEY,
  dismissOnboardingIfPresent,
} from "./helpers/session";

/**
 * Loop V72 (C2) — explicit first-visit + dismiss for coach marks.
 * Journey specs seed alphaedge.coachmarks.v1 via skipOnboarding; this file
 * deliberately does NOT, so the Getting-started card is exercised once.
 */
test.describe("Coach marks first-visit", () => {
  test("shows Getting started on first visit and persists dismiss", async ({
    page,
  }) => {
    // Seed only onboarding — leave coach-marks unset so the card appears.
    await page.addInitScript(() => {
      try {
        localStorage.setItem("alphaedge.onboarded", "true");
        // Loop 104 added the OnboardingTour (z-100) gated on this key; without
        // it the tour covers the coach marks (z-40) and the test times out.
        localStorage.setItem("ae_onboarded_v1", "true");
        // Init scripts rerun on EVERY navigation (including the reload at the
        // end of this test) — clear the seen-flag only on the first load, or
        // the dismissal can never persist across the reload assertion.
        if (!sessionStorage.getItem("e2e.coachmarks.seeded")) {
          sessionStorage.setItem("e2e.coachmarks.seeded", "true");
          localStorage.removeItem("alphaedge.coachmarks.v1");
        }
      } catch {
        /* ignore */
      }
    });

    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    const tips = page.getByRole("complementary", { name: /Getting started/i });
    await expect(tips).toBeVisible({ timeout: 15_000 });

    // Desktop: full card with Got it. Narrow: may be collapsed chip first.
    const gotIt = page.getByRole("button", { name: /^Got it$/i });
    const openTips = page.getByRole("button", {
      name: /Open getting-started tips/i,
    });
    if (await openTips.isVisible().catch(() => false)) {
      await openTips.click();
    }
    await expect(gotIt).toBeVisible({ timeout: 10_000 });
    await gotIt.click();

    await expect(tips).toHaveCount(0);

    const stored = await page.evaluate(
      (key) => localStorage.getItem(key),
      COACHMARKS_SEEN_KEY,
    );
    expect(stored).toBe("true");

    await page.reload({ waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);
    await expect(
      page.getByRole("complementary", { name: /Getting started/i }),
    ).toHaveCount(0);
  });
});
