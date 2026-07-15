import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { dismissOnboardingIfPresent, signupPaperUser, skipOnboarding } from "./helpers/session";

/**
 * Q8 — A11y pass with @axe-core/playwright.
 * Surfaces: /, market detail, /portfolio, /leaderboard.
 * Fail the suite only on serious+critical violations.
 * moderate/minor are logged + filed as BUG REPORTS in STATE.md.
 *
 * Known defects filtered from the fail set (still logged). Do not expand
 * without a matching BUG REPORT in goals/loop-v28-qa2/STATE.md (or prior).
 * - BUG-V18-02: accent contrast (fixed loop16 V9 — filter inert)
 * - BUG-V28-02: fixed loop30 — TradingView logo moved outside role=img;
 *   filter removed 2026-07-15.
 */

const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

type AxeViolation = {
  id: string;
  impact?: string | null;
  description: string;
  help: string;
  helpUrl: string;
  nodes: Array<{
    target: string[];
    html?: string;
    any?: Array<{
      data?: { bgColor?: string; fgColor?: string; contrastRatio?: number };
    }>;
  }>;
};

/** BUG-V18-02 fixed (loop16 V9) — carve-out kept inert. */
function isKnownAccentContrast(_v: AxeViolation): boolean {
  return false;
}

function isKnownA11yBug(v: AxeViolation): boolean {
  return isKnownAccentContrast(v);
}

function summarize(violations: AxeViolation[]): string {
  return violations
    .map((v) => {
      const targets = v.nodes
        .slice(0, 4)
        .map((n) => n.target.join(" "))
        .join("; ");
      return `[${v.impact ?? "?"}] ${v.id}: ${v.help} → ${targets}`;
    })
    .join("\n");
}

async function runAxe(page: Page, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissOnboardingIfPresent(page);
  await expect(page.locator("body")).toBeVisible();
  await page.waitForTimeout(2000);

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const all = results.violations as AxeViolation[];
  const known = all.filter(isKnownA11yBug);
  const serious = all.filter(
    (v) =>
      (v.impact === "serious" || v.impact === "critical") && !isKnownA11yBug(v),
  );
  const residual = all.filter(
    (v) =>
      v.impact !== "serious" &&
      v.impact !== "critical" &&
      !isKnownA11yBug(v),
  );

  if (known.length > 0) {
    console.log(
      `\n[A11Y known bug (filtered) on ${path}]\n${summarize(known)}\n`,
    );
  }
  if (residual.length > 0) {
    console.log(
      `\n[A11Y residual on ${path} — moderate/minor, not failing suite]\n${summarize(residual)}\n`,
    );
  }

  expect(
    serious,
    `serious/critical a11y violations on ${path}:\n${summarize(serious)}`,
  ).toEqual([]);

  return { serious, residual, known, all };
}

test.describe("Q8 a11y (@axe-core/playwright)", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("/ discover has no serious/critical axe violations", async ({ page }) => {
    test.setTimeout(120_000);
    await runAxe(page, "/");
  });

  test("market detail has no serious/critical axe violations", async ({ page }) => {
    test.setTimeout(120_000);
    await runAxe(page, `/markets/${CANONICAL_SLUG}`);
  });

  test("/portfolio (authed) has no serious/critical axe violations", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await signupPaperUser(page);
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible({
      timeout: 20_000,
    });
    await page.waitForTimeout(2000);

    // Reuse runAxe path logic without re-navigation losing session.
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const all = results.violations as AxeViolation[];
    const known = all.filter(isKnownA11yBug);
    const serious = all.filter(
      (v) =>
        (v.impact === "serious" || v.impact === "critical") && !isKnownA11yBug(v),
    );
    const residual = all.filter(
      (v) =>
        v.impact !== "serious" &&
        v.impact !== "critical" &&
        !isKnownA11yBug(v),
    );
    if (known.length > 0) {
      console.log(
        `\n[A11Y known bug (filtered) on /portfolio]\n${summarize(known)}\n`,
      );
    }
    if (residual.length > 0) {
      console.log(
        `\n[A11Y residual on /portfolio — moderate/minor, not failing suite]\n${summarize(residual)}\n`,
      );
    }
    expect(
      serious,
      `serious/critical a11y violations on /portfolio:\n${summarize(serious)}`,
    ).toEqual([]);
  });

  test("/leaderboard has no serious/critical axe violations", async ({ page }) => {
    test.setTimeout(120_000);
    await runAxe(page, "/leaderboard");
  });

  test("BUG-V28-02: market chart has no nested-interactive from TradingView logo", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await skipOnboarding(page);
    await page.goto(`/markets/${CANONICAL_SLUG}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    // Wait for chart canvas + attribution sibling to mount.
    await expect(
      page.getByRole("img", { name: /Price history chart/i }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("link", { name: /^TradingView$/i }).first()).toBeVisible();
    // Vendor #tv-attr-logo must not nest inside role=img.
    await expect(page.locator('#tv-attr-logo')).toHaveCount(0);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const nested = (results.violations as AxeViolation[]).filter(
      (v) =>
        v.id === "nested-interactive" &&
        (v.impact === "serious" || v.impact === "critical"),
    );
    expect(
      nested,
      `nested-interactive still present:\n${summarize(nested)}`,
    ).toEqual([]);
  });
});
