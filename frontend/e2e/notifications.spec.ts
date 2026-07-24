import { test, expect, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { skipOnboarding } from "./helpers/session";

/**
 * Loop V90 (C2) — notification center proof, mock-driven and backend-free.
 *
 * The frozen loop90 contract client (frontend/src/lib/notifications-api.ts)
 * is live-first with a MANDATORY PAPER mock fallback. We abort every API
 * route (/health probe, /api/v1/*, the HF Space host) so the run always
 * exercises the mock path: the bell renders with a mint unread badge, the
 * dropdown opens with the seeded PAPER notifications, item links work,
 * prefs toggles render, and "Mark all read" clears the badge.
 */

/** Force offline/mock mode regardless of whatever backend may be running. */
async function forceMockMode(page: Page): Promise<void> {
  await page.route((url) => {
    const href = url.toString();
    return (
      href.includes("/api/v1/") || href.includes("/health") || href.includes("hf.space")
    );
  }, (route) => route.abort());
}

function notifBell(page: Page) {
  return page.getByRole("button", { name: /Notifications/i });
}

async function unreadFromBell(page: Page): Promise<number> {
  const label = (await notifBell(page).getAttribute("aria-label")) ?? "";
  const match = label.match(/(\d+)\s+unread/i);
  if (match) return Number(match[1]);
  if (/9\+\s+unread/i.test(label)) return 9;
  return 0;
}

test.describe("Loop V90 C2 — notification center", () => {
  test("bell renders, dropdown opens from mock, mark-all clears badge", async ({ page }) => {
    test.setTimeout(180_000);

    const errors = collectConsoleErrors(page);
    await skipOnboarding(page);
    await forceMockMode(page);

    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 90_000 });

    // ── Bell renders with the mock unread badge ──────────────────────────
    await expect(notifBell(page)).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(() => unreadFromBell(page), { timeout: 20_000 })
      .toBeGreaterThanOrEqual(1);
    await expect(page.getByTestId("notification-badge")).toBeVisible();

    // ── Dropdown opens from the mock ─────────────────────────────────────
    await notifBell(page).click();
    const center = page.getByRole("region", { name: /Notification center/i });
    await expect(center).toBeVisible({ timeout: 10_000 });
    await expect(center.getByRole("heading", { name: /Notifications/i })).toBeVisible();
    await expect(center.getByText(/Whale flow/i).first()).toBeVisible({ timeout: 10_000 });
    await expect(center.getByText(/paper mock/i).first()).toBeVisible();

    // Each seeded item links via its `link` (first → canonical market).
    const firstItem = center.locator("ul li").first();
    await expect(firstItem.locator("a")).toHaveAttribute(
      "href",
      "/markets/nba-2025-01-15-lal-bos",
    );

    // Preferences toggles render in-dropdown (email_digest/in_app/fired_alerts).
    await expect(center.getByRole("switch")).toHaveCount(3);

    // C3: the useLivePrices polling hook is wired visibly (mock mode here).
    const chip = center.getByTestId("live-price-chip");
    await expect(chip).toBeVisible({ timeout: 10_000 });
    await expect(chip.getByText(/¢|—/)).toBeVisible();

    // ── Mark-all clears the badge ────────────────────────────────────────
    const markAll = center.getByRole("button", { name: /Mark all read/i });
    await expect(markAll).toBeVisible();
    await markAll.click();
    await expect
      .poll(() => unreadFromBell(page), { timeout: 15_000 })
      .toBe(0);
    await expect(notifBell(page)).toHaveAttribute("aria-label", /^Notifications$/i);
    await expect(page.getByTestId("notification-badge")).toHaveCount(0);
    await expect(center.getByRole("button", { name: /Mark all read/i })).toHaveCount(0);

    assertNoConsoleErrors(errors, "loop90 C2 notification center");
  });
});
