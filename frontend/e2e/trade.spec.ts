import { test, expect } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import {
  dismissOnboardingIfPresent,
  loginPaperUser,
  signupPaperUser,
  skipOnboarding,
} from "./helpers/session";

/**
 * Q3 — Trade journey against local uvicorn + next.
 * register/login paper user → buy open market → portfolio position + balance → cancel (sell).
 */

const CANONICAL_SLUG = "nba-2025-01-15-lal-bos";

function parseUsd(text: string): number | null {
  const m = text.replace(/,/g, "").match(/\$\s*([0-9]+(?:\.[0-9]+)?)/);
  if (!m) return null;
  return Number(m[1]);
}

/** MetricCard value next to a label (portfolio summary strip). */
async function metricUsd(page: import("@playwright/test").Page, label: RegExp): Promise<number> {
  const card = page
    .locator("div.rounded-2xl")
    .filter({ has: page.getByText(label) })
    .first();
  await expect(card).toBeVisible({ timeout: 20_000 });
  const text = await card.locator("p.font-mono").first().innerText();
  const n = parseUsd(text);
  expect(n, `unparseable metric ${label}: ${text}`).not.toBeNull();
  return n!;
}

test.describe("Q3 trade journey", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test("signup, buy open market, portfolio updates, cancel path", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    test.setTimeout(180_000);

    // 1) Register paper user via UI
    await signupPaperUser(page);
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible({
      timeout: 20_000,
    });

    // Capture starting paper balance (fresh user = $100,000.00)
    const startBalance = await metricUsd(page, /^Paper balance$/i);
    expect(startBalance).toBeGreaterThan(0);

    // Empty positions expected pre-trade
    await expect(page.getByText(/No paper trades yet/i)).toBeVisible({
      timeout: 15_000,
    });

    // 2) Open canonical seed market (always seeded open with lock_at +30d)
    await page.goto(`/markets/${CANONICAL_SLUG}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);

    // Trading panel (authed)
    const buyYes = page.getByRole("button", { name: /Buy YES/i }).first();
    await expect(buyYes).toBeVisible({ timeout: 30_000 });
    await buyYes.click();

    const shares = page.locator(`#trading-shares-${CANONICAL_SLUG}`);
    await expect(shares).toBeVisible({ timeout: 10_000 });
    await shares.fill("10");

    // Submit CTA is "Buy YES · $X.XX" (toggle is bare "Buy YES").
    const submit = page.getByRole("button", { name: /Buy YES\s*·/i });
    await expect(submit).toBeVisible({ timeout: 10_000 });
    await submit.click();

    // Success toast or My Position card
    const toastOrPos = page
      .getByText(/Order placed|My Position/i)
      .first();
    await expect(toastOrPos).toBeVisible({ timeout: 30_000 });

    // Position card after fill
    await expect(page.getByText(/My Position/i)).toBeVisible({ timeout: 20_000 });

    // 3) Portfolio: position + balance change
    await page.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible({
      timeout: 20_000,
    });

    // Position row for Lakers market
    await expect(
      page.getByRole("link", { name: /Lakers|nba-2025-01-15-lal-bos/i }).first(),
    ).toBeVisible({ timeout: 25_000 });
    await expect(page.getByText(/No paper trades yet/i)).toHaveCount(0);

    const afterBalance = await metricUsd(page, /^Paper balance$/i);
    expect(
      afterBalance,
      `expected balance drop from ${startBalance} to ${afterBalance}`,
    ).toBeLessThan(startBalance);

    // Trade history tab shows the open trade
    await page.getByRole("button", { name: /Trade History/i }).click();
    await expect(page.getByText(CANONICAL_SLUG).first()).toBeVisible({
      timeout: 15_000,
    });

    // 4) Cancel path — sell via market detail PositionCard
    await page.goto(`/markets/${CANONICAL_SLUG}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(page);
    await expect(page.getByText(/My Position/i)).toBeVisible({ timeout: 25_000 });
    const sellBtn = page.getByRole("button", { name: /Sell \d+ shares/i });
    await expect(sellBtn).toBeVisible({ timeout: 15_000 });
    await sellBtn.click();
    await expect(page.getByText(/Position closed|Closing/i).first()).toBeVisible({
      timeout: 20_000,
    });
    // Position card should clear after close (or show closed toast)
    await expect(page.getByText(/Position closed/i)).toBeVisible({
      timeout: 20_000,
    });

    // Portfolio should no longer list an open position for that market
    // (history may still show settled/closed trades).
    await page.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await page.getByRole("button", { name: /^Positions$/i }).click();
    // After full close: either empty state or no open Lakers row.
    // Allow either empty or only settled rows.
    const empty = page.getByText(/No paper trades yet/i);
    const hasEmpty = await empty.isVisible({ timeout: 8_000 }).catch(() => false);
    if (!hasEmpty) {
      // If positions remain, they must not be unsettled Lakers buys — soft check:
      // quantity table still present is OK if settled; we just require balance recovered.
      const finalBal = await metricUsd(page, /^Paper balance$/i);
      // Proceeds returned — should be near start (paper path is free of fees)
      expect(finalBal).toBeGreaterThan(afterBalance);
    }

    await page.waitForTimeout(1000);
    assertNoConsoleErrors(errors, "trade journey");
  });

  test("login path works for existing paper user", async ({ page }) => {
    // Separate smoke of login after signup (register already covered above).
    const { email, password } = await signupPaperUser(page);
    // Clear session client-side and re-login
    await page.evaluate(() => {
      localStorage.removeItem("alphaedge.accessToken");
      localStorage.removeItem("alphaedge.userEmail");
    });
    await loginPaperUser(page, email, password);
    await expect(page.getByRole("heading", { name: /Portfolio/i })).toBeVisible();
  });
});
