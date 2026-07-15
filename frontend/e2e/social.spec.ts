import { test, expect, type Browser, type Page } from "@playwright/test";
import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import {
  CANONICAL_SLUG,
  paperBuyCanonical,
  setDisplayName,
  setProfilePublicViaSqlite,
} from "./helpers/local-api";
import {
  dismissOnboardingIfPresent,
  signupPaperUser,
  skipOnboarding,
  uniqueEmail,
} from "./helpers/session";

/**
 * G1 — Social journeys (Loop V28).
 * signup A+B → B trades → A follows B from profile → Following tab shows B;
 * profile stats render; unfollow works; opt-out hides profile.
 */

async function newAuthedPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await skipOnboarding(page);
  return page;
}

test.describe("G1 social journeys", () => {
  test("A follows B, Following tab, profile stats, unfollow, opt-out hide", async ({
    browser,
  }) => {
    test.setTimeout(240_000);

    const suffix = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
    const displayB = `L28B${suffix}`.slice(0, 32);
    const emailB = uniqueEmail("loop28-b");
    const emailA = uniqueEmail("loop28-a");
    const password = "Loop28qa!";

    // ── User B: signup, set public handle, paper trade ──
    const pageB = await newAuthedPage(browser);
    const errorsB = collectConsoleErrors(pageB);
    await signupPaperUser(pageB, { email: emailB, password });
    await setDisplayName(pageB, displayB);
    await paperBuyCanonical(pageB, 5);
    assertNoConsoleErrors(errorsB, "social B setup");

    // ── User A: signup, open B's profile, follow ──
    const pageA = await newAuthedPage(browser);
    const errorsA = collectConsoleErrors(pageA);
    await signupPaperUser(pageA, { email: emailA, password });

    // Prefer profile path (leaderboard may still show demo-only rows until settled).
    await pageA.goto(`/traders/${encodeURIComponent(displayB)}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(pageA);

    await expect(
      pageA.getByRole("heading", { name: new RegExp(displayB, "i") }).first(),
    ).toBeVisible({ timeout: 25_000 });

    // Profile stats tiles
    await expect(pageA.getByText(/^Win rate$/i).first()).toBeVisible();
    await expect(pageA.getByText(/^ROI$/i).first()).toBeVisible();
    await expect(pageA.getByText(/^Followers$/i).first()).toBeVisible();
    await expect(pageA.getByText(/^All trades$/i).first()).toBeVisible();

    const followBtn = pageA.getByRole("button", { name: /Follow trader/i });
    await expect(followBtn).toBeVisible({ timeout: 15_000 });
    await followBtn.click();
    await expect(
      pageA.getByRole("button", { name: /Unfollow/i }),
    ).toBeVisible({ timeout: 15_000 });

    // Followers count should reflect at least 1 after follow
    const followersTile = pageA
      .locator("dl")
      .filter({ has: pageA.getByText(/^Followers$/i) })
      .first();
    await expect(followersTile).toBeVisible();
    const followersText = await followersTile.innerText();
    expect(followersText).toMatch(/[1-9]/);

    // ── Following tab shows B's paper trade ──
    await pageA.goto("/feed?view=following", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await dismissOnboardingIfPresent(pageA);
    await expect(
      pageA.getByRole("navigation", { name: /Feed views/i }).getByRole("link", {
        name: /^Following$/i,
      }),
    ).toHaveAttribute("aria-current", "page");

    const followingFeed = pageA.getByRole("region", {
      name: /Followed trader activity/i,
    });
    await expect(followingFeed).toBeVisible({ timeout: 25_000 });
    // Activity from followed B is present (slug + trader link).
    await expect(followingFeed.getByText(CANONICAL_SLUG).first()).toBeVisible({
      timeout: 15_000,
    });
    const traderLink = followingFeed.getByRole("link").first();
    await expect(traderLink).toBeVisible();
    const traderLabel = (await traderLink.innerText()).trim();
    // BUG-V28-01 fixed: feed respects display_name (same rule as profiles/leaderboard).
    expect(traderLabel, "followed-trade trader label").toMatch(new RegExp(displayB, "i"));
    await expect(traderLink).toHaveAttribute(
      "href",
      new RegExp(`/traders/${encodeURIComponent(displayB)}`, "i"),
    );

    // ── Unfollow works ──
    await pageA.goto(`/traders/${encodeURIComponent(displayB)}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    const unfollowBtn = pageA.getByRole("button", { name: /Unfollow/i });
    await expect(unfollowBtn).toBeVisible({ timeout: 15_000 });
    await unfollowBtn.click();
    await expect(
      pageA.getByRole("button", { name: /Follow trader/i }),
    ).toBeVisible({ timeout: 15_000 });

    // After unfollow, Following feed is honest-empty (no remaining follows)
    await pageA.goto("/feed?view=following", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(
      pageA.getByText(/No followed-trader activity yet|Follow traders/i).first(),
    ).toBeVisible({ timeout: 20_000 });

    // ── Opt-out hides profile (no UI; set via local e2e SQLite) ──
    setProfilePublicViaSqlite(emailB, false);
    await pageA.goto(`/traders/${encodeURIComponent(displayB)}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(
      pageA.getByRole("heading", { name: /Profile not available/i }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(
      pageA.getByText(/unavailable or private|opted out|unknown/i).first(),
    ).toBeVisible();

    await pageA.waitForTimeout(800);
    assertNoConsoleErrors(errorsA, "social A journeys");

    await pageB.context().close();
    await pageA.context().close();
  });

  // BUG-V28-01 covered by the main journey assertion above (display_name on Following feed).
});
