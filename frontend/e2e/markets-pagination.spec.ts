import { expect, test, type Page, type Route } from "@playwright/test";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

/**
 * Loop 105 — markets catalog pagination UI (Load more).
 * Local Playwright stack only. Intercepts GET /api/v1/markets so the small
 * seed catalog can still exercise limit/offset + X-Total-Count.
 * PAPER_TRADING_ONLY — read-only surface, no order path.
 */

const TOTAL = 250;
const PAGE_LIMIT = 100;

type FakeMarket = {
  id: string;
  slug: string;
  title: string;
  question: string;
  status: "open";
  lock_at: string;
  resolved_at: null;
  winning_outcome: null;
  category: string;
  icon: string;
  volume: number;
  traders: number;
  market_count: number;
  description: string;
  resolution: string;
  source: string;
  yes_price: number;
};

function makeMarket(i: number): FakeMarket {
  // Keep prices in (0.01, 0.99) so activeTrendingMarkets keeps rows visible.
  const yes = 0.35 + (i % 40) / 100;
  return {
    id: `loop105-${i}`,
    slug: `pm-loop105-page-${String(i).padStart(3, "0")}`,
    title: `Loop105 Market ${i} vs Rival`,
    question: `Will Loop105 Market ${i} resolve YES?`,
    status: "open",
    lock_at: "2027-06-01T00:00:00Z",
    resolved_at: null,
    winning_outcome: null,
    category: "Sports",
    icon: "🏀",
    volume: 10_000 + i * 10,
    traders: 100 + i,
    market_count: 1,
    description: "Paper-trading simulation market for pagination e2e.",
    resolution: "Resolves YES/NO per paper rules.",
    source: "polymarket",
    yes_price: yes,
  };
}

function parsePaging(url: URL): { limit: number; offset: number } {
  const limitRaw = Number(url.searchParams.get("limit") ?? String(PAGE_LIMIT));
  const offsetRaw = Number(url.searchParams.get("offset") ?? "0");
  const limit = Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 500) : PAGE_LIMIT;
  const offset = Number.isFinite(offsetRaw) ? Math.max(offsetRaw, 0) : 0;
  return { limit, offset };
}

async function fulfillMarketsPage(route: Route): Promise<void> {
  const url = new URL(route.request().url());
  const { limit, offset } = parsePaging(url);
  const end = Math.min(offset + limit, TOTAL);
  const items = [];
  for (let i = offset; i < end; i++) items.push(makeMarket(i));
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: {
      "X-Total-Count": String(TOTAL),
      "X-Page-Limit": String(limit),
      "X-Page-Offset": String(offset),
      "Access-Control-Expose-Headers": "X-Total-Count, X-Page-Limit, X-Page-Offset",
    },
    body: JSON.stringify(items),
  });
}

async function installMarketsPaginationMock(page: Page): Promise<void> {
  await page.route("**/api/v1/markets**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/+$/, "");
    if (path !== "/api/v1/markets") {
      await route.continue();
      return;
    }
    await fulfillMarketsPage(route);
  });
}

async function openMarkets(page: Page): Promise<void> {
  await page.goto("/markets", { waitUntil: "domcontentloaded", timeout: 60_000 });
  await dismissOnboardingIfPresent(page);
}

test.describe("Loop 105 markets pagination", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await page.addInitScript(() => {
      try {
        localStorage.setItem("ae_onboarded_v1", "true");
      } catch {
        /* ignore */
      }
    });
    await installMarketsPaginationMock(page);
  });

  test("markets_page_load_more_appends_and_reports_total", async ({ page }) => {
    await openMarkets(page);

    const showing = page.getByText(/Showing\s+\d+\s+of\s+250\s+markets/i);
    await expect(showing).toBeVisible({ timeout: 30_000 });
    await expect(showing).toContainText(/Showing\s+100\s+of\s+250\s+markets/i);

    const loadMore = page.getByRole("button", { name: /^Load more$/i });
    await expect(loadMore).toBeVisible();

    const linksBefore = await page.locator('a[href*="pm-loop105-page-"]').count();
    expect(linksBefore).toBeGreaterThan(0);

    await loadMore.click();
    await expect(page.getByText(/Showing\s+200\s+of\s+250\s+markets/i)).toBeVisible({
      timeout: 20_000,
    });

    const linksAfter = await page.locator('a[href*="pm-loop105-page-"]').count();
    expect(linksAfter).toBeGreaterThan(linksBefore);
    await expect(page.getByRole("button", { name: /^Load more$/i })).toBeVisible();
  });

  test("markets_page_load_more_hides_when_all_loaded", async ({ page }) => {
    await openMarkets(page);

    await expect(page.getByText(/Showing\s+100\s+of\s+250\s+markets/i)).toBeVisible({
      timeout: 30_000,
    });

    await page.getByRole("button", { name: /^Load more$/i }).click();
    await expect(page.getByText(/Showing\s+200\s+of\s+250\s+markets/i)).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole("button", { name: /^Load more$/i }).click();
    await expect(page.getByText(/Showing\s+250\s+of\s+250\s+markets/i)).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("button", { name: /^Load more$/i })).toHaveCount(0);
  });
});
