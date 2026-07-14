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
  use: {
    baseURL: PLAYWRIGHT_BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
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
