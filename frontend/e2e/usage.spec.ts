import { expect, test } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop V85 (D-U2, G3) — /usage DOM-assertion spec.
 * The usage client falls back to a deterministic in-memory paper mock when
 * the live API is offline, so the stat cards, stacked chart, and the 14-day
 * log all render without the backend (dev-server-only path, like V83/V84).
 */

// Pre-existing site-wide noise, NOT from /usage: when the shared live
// markets API degrades (HF free tier 503), the SiteHeader/ticker markets
// probe rejects unhandled and surfaces as a pageerror on EVERY page —
// verified firing identically on /skills in the same environment. The usage
// page must still add zero errors of its own, so filter exactly that one
// signature and keep everything else strict.
const PREEXISTING_MARKETS_PROBE_NOISE = /Markets HTTP 503/;

test.describe("V85 usage dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/usage renders 4 stat cards and table rows from the mock", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/usage", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("usage-page")).toBeVisible({ timeout: 30_000 });

    // Ticket-mandated header label.
    await expect(
      page.getByRole("heading", { name: "Usage — paper research activity" }),
    ).toBeVisible({ timeout: 20_000 });

    // Exactly 4 stat cards (sessions / skill runs / scanner runs / briefs),
    // each carrying a count-up value node.
    const cards = page.getByTestId("usage-stat-card");
    await expect(cards.first()).toBeVisible({ timeout: 30_000 });
    await expect(cards).toHaveCount(4);
    for (const key of ["sessions", "skill_runs", "scanner_runs", "briefs"]) {
      await expect(page.getByTestId(`usage-stat-${key}-value`)).toBeVisible();
    }

    // >=1 table row from the mock (the mock seeds exactly 14 calendar days).
    const rows = page.getByTestId("usage-table-row");
    await expect(rows.first()).toBeVisible({ timeout: 20_000 });
    expect(await rows.count()).toBeGreaterThanOrEqual(1);

    // Stacked chart canvas shell is present with reserved height.
    await expect(page.getByTestId("usage-chart")).toBeVisible();

    // Loop V86 X4 — "Paper research usage" / Runs-by-surface breakdown card:
    // 4 per-metric surface cards, each with a sparkline and a count-up value.
    await expect(page.getByTestId("usage-by-surface")).toBeVisible();
    const surfaceCards = page.getByTestId("usage-surface-card");
    await expect(surfaceCards).toHaveCount(4);
    for (const key of ["sessions", "skill_runs", "scanner_runs", "briefs"]) {
      await expect(page.getByTestId(`usage-surface-${key}-value`)).toBeVisible();
    }
    await expect(page.getByTestId("usage-sparkline").first()).toBeVisible();

    await page.waitForTimeout(500);
    assertNoConsoleErrors(
      errors.filter((e) => !PREEXISTING_MARKETS_PROBE_NOISE.test(e)),
      "/usage",
    );
  });
});
