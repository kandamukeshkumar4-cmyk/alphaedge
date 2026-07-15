import { defineConfig, devices } from "@playwright/test";

/**
 * Loop V17 — local-stack Playwright config.
 *
 * Default: boot real uvicorn (isolated SQLite) + next dev via
 * e2e/helpers/start-local-stack.mjs. Never targets prod Railway.
 *
 * Override: set PLAYWRIGHT_BASE_URL to hit an already-running local stack
 * (then set E2E_SKIP_WEBSERVER=1).
 */
const FE_PORT = Number(process.env.E2E_FE_PORT || 31017);
const API_PORT = Number(process.env.E2E_API_PORT || 18017);
const PLAYWRIGHT_BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL?.trim() || `http://127.0.0.1:${FE_PORT}`;
const SKIP_WEBSERVER =
  process.env.E2E_SKIP_WEBSERVER === "1" ||
  (!!process.env.PLAYWRIGHT_BASE_URL &&
    !process.env.PLAYWRIGHT_BASE_URL.includes("127.0.0.1") &&
    !process.env.PLAYWRIGHT_BASE_URL.includes("localhost"));

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  // S3: platform-tag baselines so ubuntu CI and Windows-local never collide.
  // Visreg shots live under e2e/visreg.spec.ts-snapshots/…-{platform}.png
  snapshotPathTemplate:
    "{testDir}/{testFilePath}-snapshots/{arg}-{projectName}-{platform}{ext}",
  use: {
    baseURL: PLAYWRIGHT_BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    // Existing suite (CI: --project=chromium). Visreg excluded so missing
    // ubuntu baseline PNGs cannot break the green CI job.
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /visreg\.spec\.ts/,
    },
    // Local-only visual regression. Generate/update:
    //   npx playwright test --project=visreg --update-snapshots
    // Documented in goals/loop-v44-visreg/STATE.md — not wired into ci-e2e
    // (ubuntu baselines would require a non-trivial workflow change).
    {
      name: "visreg",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /visreg\.spec\.ts/,
    },
  ],
  ...(SKIP_WEBSERVER
    ? {}
    : {
        webServer: {
          command: "node e2e/helpers/start-local-stack.mjs",
          url: PLAYWRIGHT_BASE_URL,
          timeout: 180_000,
          reuseExistingServer: !process.env.CI,
          env: {
            E2E_API_PORT: String(API_PORT),
            E2E_FE_PORT: String(FE_PORT),
          },
        },
      }),
});
