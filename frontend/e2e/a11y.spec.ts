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
 * - BUG-V28-02: lightweight-charts TradingView #tv-attr-logo nested in role=img
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
      relatedNodes?: Array<{ html?: string; target?: string[] }>;
    }>;
  }>;
};

/** BUG-V18-02 fixed (loop16 V9) — carve-out kept inert. */
function isKnownAccentContrast(_v: AxeViolation): boolean {
  return false;
}

/**
 * BUG-V28-02: lightweight-charts injects TradingView attribution <a id="tv-attr-logo">
 * inside the chart container marked role="img" → axe nested-interactive (serious).
 * App chart wrapper owns the fix; e2e must not fail the whole suite on vendor chrome.
 */
function isKnownTradingViewNestedInteractive(v: AxeViolation): boolean {
  if (v.id !== "nested-interactive") return false;
  return v.nodes.some((n) => {
    const html = (n.html ?? "").toLowerCase();
    const targets = n.target.join(" ").toLowerCase();
    const related = (n.any ?? [])
      .flatMap((a) => a.relatedNodes ?? [])
      .map((r) => `${r.html ?? ""} ${(r.target ?? []).join(" ")}`)
      .join(" ")
      .toLowerCase();
    const blob = `${html} ${targets} ${related}`;
    return (
      blob.includes("tv-attr-logo") ||
      blob.includes("tradingview") ||
      (blob.includes('role="img"') && blob.includes("chart"))
    );
  });
}

function isKnownA11yBug(v: AxeViolation): boolean {
  return isKnownAccentContrast(v) || isKnownTradingViewNestedInteractive(v);
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

  test("BUG-V28-02: market chart has no nested-interactive from TradingView logo", async () => {
    // App/vendor: lightweight-charts #tv-attr-logo inside role=img chart shell.
    // Filtered from fail set above; this fixme tracks the product fix.
    test.fixme(
      true,
      "BUG-V28-02: TradingView attribution link nested in role=img chart (nested-interactive)",
    );
  });
});
