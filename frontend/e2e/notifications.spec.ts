import { test, expect, type Browser, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import {
  CANONICAL_SLUG,
  paperBuyCanonical,
  setDisplayName,
} from "./helpers/local-api";
import {
  dismissOnboardingIfPresent,
  signupPaperUser,
  skipOnboarding,
  uniqueEmail,
} from "./helpers/session";

/**
 * G2 — Notification journeys (Loop V28).
 * After follow + followed-trade: A's bell shows unread badge; open center;
 * mark-one and mark-all; badge clears.
 *
 * Note: WS-driven live bump is best-effort on local stack; assertions use
 * poll-based GET via NotificationBell mount (honest).
 */

async function newAuthedPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await skipOnboarding(page);
  return page;
}

function notifBell(page: Page) {
  return page.getByRole("button", { name: /Notifications/i });
}

async function unreadFromBell(page: Page): Promise<number> {
  const label = (await notifBell(page).getAttribute("aria-label")) ?? "";
  const m = label.match(/(\d+)\s+unread/i);
  if (m) return Number(m[1]);
  if (/9\+\s+unread/i.test(label)) return 9;
  return 0;
}

async function openNotifCenter(page: Page) {
  await notifBell(page).click();
  const center = page.getByRole("region", { name: /Notification center/i });
  await expect(center).toBeVisible({ timeout: 10_000 });
  return center;
}

async function waitForUnread(page: Page, min = 1, timeout = 45_000) {
  await expect
    .poll(() => unreadFromBell(page), {
      timeout,
      intervals: [400, 800, 1500],
    })
    .toBeGreaterThanOrEqual(min);
}

test.describe("G2 notification journeys", () => {
  test("unread badge after followed-trade; mark-one/mark-all; badge clears", async ({
    browser,
  }) => {
    test.setTimeout(300_000);

    const suffix = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
    const displayB = `L28N${suffix}`.slice(0, 32);
    const emailB = uniqueEmail("loop28-nb");
    const emailA = uniqueEmail("loop28-na");
    const password = "Loop28qa!";

    const pageA = await newAuthedPage(browser);
    const errorsA = collectConsoleErrors(pageA);
    await signupPaperUser(pageA, { email: emailA, password });

    const pageB = await newAuthedPage(browser);
    const errorsB = collectConsoleErrors(pageB);
    await signupPaperUser(pageB, { email: emailB, password });
    await setDisplayName(pageB, displayB);

    // A follows B before any trade (required for followed_trade fanout).
    await pageA.goto(`/traders/${encodeURIComponent(displayB)}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(pageA);
    await expect(
      pageA.getByRole("heading", { name: new RegExp(displayB, "i") }).first(),
    ).toBeVisible({ timeout: 25_000 });
    await pageA.getByRole("button", { name: /Follow trader/i }).click();
    await expect(
      pageA.getByRole("button", { name: /Unfollow/i }),
    ).toBeVisible({ timeout: 15_000 });

    // ── Trade 1 → unread badge ──
    await paperBuyCanonical(pageB, 3);
    assertNoConsoleErrors(errorsB, "notif B trade 1");

    await pageA.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(pageA);
    await waitForUnread(pageA, 1);

    let center = await openNotifCenter(pageA);
    await expect(
      center.getByRole("heading", { name: /Notifications/i }),
    ).toBeVisible();
    await expect(center.getByText(/traded/i).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(center.getByText(CANONICAL_SLUG).first()).toBeVisible();

    // ── mark-all (use header button; avoid item link navigation) ──
    const markAll = center.getByRole("button", { name: /Mark all read/i });
    await expect(markAll).toBeVisible();
    await markAll.click({ force: true });
    await expect
      .poll(() => unreadFromBell(pageA), { timeout: 20_000 })
      .toBe(0);
    // Mark-all control hides when unread_count hits 0
    await expect(
      center.getByRole("button", { name: /Mark all read/i }),
    ).toHaveCount(0);

    // Close center by clicking outside (portfolio heading)
    await pageA.getByRole("heading", { name: /Portfolio/i }).click();
    await expect(center).toBeHidden({ timeout: 5_000 }).catch(() => undefined);

    // ── Trade 2 → new unread for mark-one path ──
    await paperBuyCanonical(pageB, 2);

    await pageA.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await waitForUnread(pageA, 1);

    center = await openNotifCenter(pageA);
    const items = center.locator("ul li");
    await expect(items.first()).toBeVisible({ timeout: 15_000 });

    // mark-one: click the notification (link navigates to market)
    const firstControl = items.first().locator("a, button").first();
    await firstControl.click();

    // Land on market or stay; either way unread should drop to 0 for single item.
    await pageA.goto("/portfolio", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect
      .poll(() => unreadFromBell(pageA), { timeout: 20_000 })
      .toBe(0);
    await expect(notifBell(pageA)).toHaveAttribute(
      "aria-label",
      /^Notifications$/i,
    );

    await pageA.waitForTimeout(500);
    assertNoConsoleErrors(errorsA, "notif A journeys");

    await pageB.context().close();
    await pageA.context().close();
  });
});
