import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { dismissOnboardingIfPresent, signupPaperUser, skipOnboarding } from "./helpers/session";

/**
 * Q8 — A11y pass with @axe-core/playwright.
 * Surfaces: /, market detail, /portfolio, /leaderboard.
 * Fail the suite only on serious+critical violations.
 * moderate/minor are logged + filed as BUG REPORTS in STATE.md.
 *
 * Known theme defect BUG-V18-02 (white text on #00c9a0 accent, contrast 2.12)
 * is filtered from the fail set so other serious/critical still block the suite.
 * Do not expand the filter without a matching BUG REPORT.
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
    any?: Array<{ data?: { bgColor?: string; fgColor?: string; contrastRatio?: number } }>;
  }>;
};

/** BUG-V18-02 fixed (loop16 V9) — no known-violation carve-out remains. */
function isKnownAccentContrast(_v: AxeViolation): boolean {
  return false;
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
  const known = all.filter(isKnownAccentContrast);
  const serious = all.filter(
    (v) =>
      (v.impact === "serious" || v.impact === "critical") && !isKnownAccentContrast(v),
  );
  const residual = all.filter(
    (v) =>
      v.impact !== "serious" &&
      v.impact !== "critical" &&
      !isKnownAccentContrast(v),
  );

  if (known.length > 0) {
    console.log(
      `\n[A11Y known BUG-V18-02 on ${path} — filtered from fail set]\n${summarize(known)}\n`,
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
    const known = all.filter(isKnownAccentContrast);
    const serious = all.filter(
      (v) =>
        (v.impact === "serious" || v.impact === "critical") && !isKnownAccentContrast(v),
    );
    const residual = all.filter(
      (v) =>
        v.impact !== "serious" &&
        v.impact !== "critical" &&
        !isKnownAccentContrast(v),
    );
    if (known.length > 0) {
      console.log(
        `\n[A11Y known BUG-V18-02 on /portfolio — filtered from fail set]\n${summarize(known)}\n`,
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
});
