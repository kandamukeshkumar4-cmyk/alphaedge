import { expect, test, type Page, type Route } from "@playwright/test";

import { signupPaperUser, skipOnboarding, uniqueEmail } from "./helpers/session";

const ACTOR = {
  handle: "line-watcher",
  display_name: "Line Watcher",
  avatar_url: null,
};

const FIRST_STORY = {
  id: "story-first",
  kind: "forecast",
  actor: ACTOR,
  market_slug: "nba-2025-01-15-lal-bos",
  market_title: "Lakers vs Celtics",
  headline: "A forecast with a clear closing-line reference",
  body: "Research context only.",
  created_at: "2026-07-24T12:00:00.000Z",
  reactions: { like: 4 },
  reacted: false,
  comment_count: 0,
};

const SECOND_STORY = {
  ...FIRST_STORY,
  id: "story-second",
  kind: "note",
  market_slug: null,
  market_title: null,
  headline: "A second story arrives from the next cursor",
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockStories(page: Page, body: unknown) {
  await page.route(/\/api\/v1\/social\/stories(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await fulfillJson(route, body);
  });
}

async function visitCommunity(page: Page) {
  await page.goto("/community", { waitUntil: "domcontentloaded", timeout: 60_000 });
  await expect(page.getByRole("heading", { name: "Stories from the desk" })).toBeVisible();
}

test.describe("community stories", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await page.addInitScript(() => {
      localStorage.setItem("ae_onboarded_v1", "true");
    });
  });

  test("feed renders a story card", async ({ page }) => {
    await mockStories(page, { items: [FIRST_STORY], next_cursor: null });
    await visitCommunity(page);

    await expect(page.getByTestId("story-card-story-first")).toBeVisible();
    await expect(page.getByText(FIRST_STORY.headline)).toBeVisible();
    await expect(
      page.getByTestId("story-card-story-first").getByRole("link", { name: /Lakers vs Celtics/i }),
    ).toHaveAttribute("href", "/markets/nba-2025-01-15-lal-bos");
  });

  test("load more appends the next cursor page", async ({ page }) => {
    await page.route(/\/api\/v1\/social\/stories(?:\?.*)?$/, async (route) => {
      const cursor = new URL(route.request().url()).searchParams.get("cursor");
      await fulfillJson(
        route,
        cursor === "next-page"
          ? { items: [SECOND_STORY], next_cursor: null }
          : { items: [FIRST_STORY], next_cursor: "next-page" },
      );
    });
    await visitCommunity(page);

    await expect(page.getByRole("button", { name: "Load more" })).toBeVisible();
    await page.getByRole("button", { name: "Load more" }).click();
    await expect(page.getByTestId("story-card-story-second")).toBeVisible();
    await expect(page.getByTestId("story-card-story-first")).toBeVisible();
    await expect(page.getByRole("button", { name: "Load more" })).toHaveCount(0);
  });

  test("logged-out composer is disabled with a sign-in affordance", async ({ page }) => {
    await mockStories(page, { items: [FIRST_STORY], next_cursor: null });
    await page.route(/\/api\/v1\/social\/stories\/[^/]+\/comments(?:\?.*)?$/, async (route) => {
      await fulfillJson(route, { items: [] });
    });
    await visitCommunity(page);

    await page.getByRole("button", { name: /0 comments/i }).click();
    await expect(page.getByLabel("Add a comment")).toBeDisabled();
    await expect(page.getByRole("link", { name: "Sign in to comment" })).toBeVisible();
  });

  test("like toggles optimistically and settles from the response", async ({ page }) => {
    await signupPaperUser(page, { email: uniqueEmail("loop104-community") });
    await mockStories(page, { items: [FIRST_STORY], next_cursor: null });
    await page.route(/\/api\/v1\/social\/stories\/[^/]+\/reactions$/, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 250));
      await fulfillJson(route, { reactions: { like: 5 }, reacted: true });
    });
    await visitCommunity(page);

    const card = page.getByTestId("story-card-story-first");
    const like = card.getByRole("button", { name: "Like story" });
    await like.click();
    await expect(card.getByRole("button", { name: "Unlike story" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(card.getByRole("button", { name: "Unlike story" })).toContainText("5");
  });

  test("empty state renders when the API has no stories", async ({ page }) => {
    await mockStories(page, { items: [], next_cursor: null });
    await visitCommunity(page);

    await expect(page.getByTestId("community-empty-state")).toBeVisible();
    await expect(page.getByText("No stories yet")).toBeVisible();
  });
});
