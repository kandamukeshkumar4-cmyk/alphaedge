import { expect, test, type Page, type Route } from "@playwright/test";

import { assertNoConsoleErrors, collectConsoleErrors } from "./helpers/console";
import { dismissOnboardingIfPresent, skipOnboarding } from "./helpers/session";

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const FIXTURES = {
  briefs: {
    items: [
      {
        id: "brief-1",
        market_slug: "championship-final",
        kind: "brief",
        headline: "Championship price dislocation",
        body_markdown: "Three independent reads diverged from the closing market price.",
        citations: [{ title: "Market snapshot" }, { title: "Line history" }],
        created_at: "2026-07-24T16:00:00Z",
        claim: { status: "open" },
      },
      {
        id: "brief-2",
        market_slug: "senate-balance",
        kind: "digest",
        headline: "Daily election digest",
        body_markdown: "A persisted digest of the latest election research.",
        citations: [],
        created_at: "2026-07-23T16:00:00Z",
        claim: null,
      },
    ],
    total: 2,
    limit: 100,
    offset: 0,
  },
  memories: {
    items: [
      {
        id: "memory-1",
        market_slug: "resolved-final",
        category: "Sports",
        question: "Did the closing favorite win the final?",
        outcome: "YES",
        brier: 0.081,
        rationale_summary: "The locked forecast was graded against the resolved outcome.",
        created_at: "2026-07-22T12:00:00Z",
      },
    ],
    total: 1,
    limit: 100,
  },
  scanners: [
    {
      id: "scanner-1",
      name: "Late price movement",
      description: "Checks meaningful price movement before lock.",
      status: "active",
      is_public: false,
      updated_at: "2026-07-24T14:00:00Z",
      spec: { steps: [{ type: "PRICE_TREND" }, { type: "MODEL_EDGE" }] },
      latest_run: {
        id: "scanner-run-1",
        status: "completed",
        started_at: "2026-07-24T13:55:00Z",
        finished_at: "2026-07-24T14:00:00Z",
        result: {
          top_pick: {
            market_slug: "championship-final",
            title: "Championship final",
          },
        },
      },
    },
  ],
  alpha: {
    runs: [
      {
        id: "alpha-run-1",
        run_date: "2026-07-24",
        status: "no_signal",
        result: {
          signal: { label: "no signal (evidence)", residual_alpha_t_stat: 1.42 },
          decomposition: { residual_alpha: 0.004, residual_alpha_t_stat: 1.42 },
        },
        rejection_reasons: [{ node: "validator", reason: "threshold" }],
        paper_trading_only: true,
      },
    ],
    paper_trading_only: true,
  },
  skills: [
    {
      id: "skill-1",
      name: "Closing-line audit",
      description: "A saved workflow for comparing forecasts with the closing line.",
      template: [{ title: "Load" }, { title: "Compare" }],
      run_count: 8,
      is_public: true,
      created_at: "2026-07-20T10:00:00Z",
      updated_at: "2026-07-24T10:00:00Z",
    },
  ],
};

type SourceName = keyof typeof FIXTURES;

const SOURCE_PATTERNS: Record<SourceName, string> = {
  briefs: "**/api/v1/briefs**",
  memories: "**/api/v1/memories**",
  scanners: "**/api/v1/scanners/",
  alpha: "**/api/v1/alpha/runs**",
  skills: "**/api/v1/skills/",
};

async function routeLibrary(
  page: Page,
  options?: {
    failed?: SourceName[];
    empty?: boolean;
    waitForRelease?: Promise<void>;
  },
) {
  const failed = new Set(options?.failed ?? []);
  for (const source of Object.keys(SOURCE_PATTERNS) as SourceName[]) {
    await page.route(SOURCE_PATTERNS[source], async (route) => {
      if (options?.waitForRelease) await options.waitForRelease;
      if (failed.has(source)) {
        await fulfillJson(route, { detail: "unavailable" }, 503);
        return;
      }
      if (options?.empty) {
        const emptyBody =
          source === "briefs" || source === "memories"
            ? { items: [], total: 0, limit: 100, offset: 0 }
            : source === "alpha"
              ? { runs: [], paper_trading_only: true }
              : [];
        await fulfillJson(route, emptyBody);
        return;
      }
      await fulfillJson(route, FIXTURES[source]);
    });
  }
}

test.describe("Loop 104 live research library", () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await page.addInitScript(() => {
      localStorage.setItem("ae_onboarded_v1", "true");
    });
  });

  test("live artifacts load without substitution and remain filterable", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    let releaseReads: () => void = () => {};
    const readsReleased = new Promise<void>((resolve) => {
      releaseReads = resolve;
    });
    await routeLibrary(page, { waitForRelease: readsReleased });
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-loading")).toBeVisible();
    releaseReads();
    await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
    await expect(page.getByText("5 of 5 live sources responded.")).toBeVisible();
    await expect(page.getByTestId("library-card")).toHaveCount(6);

    await page.getByTestId("library-filter-report").click();
    await expect(page.getByTestId("library-card")).toHaveCount(1);
    await expect(page.getByTestId("library-card")).toHaveAttribute("data-kind", "report");

    await page.getByTestId("library-filter-all").click();
    await page.getByLabel("Find research").fill("championship");
    await expect(page.getByTestId("library-card")).toHaveCount(2);
    await expect(page.getByText("Championship price dislocation")).toBeVisible();

    await page.getByLabel("Find research").fill("");
    await page.getByTestId("library-filter-alpha").click();
    await expect(page.getByTestId("library-card")).toHaveCount(1);
    await expect(page.getByTestId("library-card")).toContainText("no signal");

    assertNoConsoleErrors(errors, "/library");
  });

  test("one failed source is named while available research stays browsable", async ({
    page,
  }) => {
    await routeLibrary(page, { failed: ["scanners"] });
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-partial-error")).toContainText(
      "Scanners did not respond",
    );
    await expect(page.getByText("4 of 5 live sources responded.")).toBeVisible();
    await expect(page.getByTestId("library-card")).toHaveCount(5);
  });

  test("five empty live sources render the deliberate empty archive", async ({ page }) => {
    await routeLibrary(page, { empty: true });
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-empty")).toBeVisible();
    await expect(page.getByText("No persisted research yet")).toBeVisible();
    await expect(page.getByTestId("library-card")).toHaveCount(0);
  });

  test("a total outage renders an error and never fabricates cards", async ({ page }) => {
    await routeLibrary(page, {
      failed: ["briefs", "memories", "scanners", "alpha", "skills"],
    });
    await page.goto("/library", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByTestId("library-error")).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry live sources" })).toBeVisible();
    await expect(page.getByTestId("library-card")).toHaveCount(0);
  });
});
