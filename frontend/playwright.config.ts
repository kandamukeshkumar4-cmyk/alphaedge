import { defineConfig, devices } from "@playwright/test";

// E2E runs against a locally served PRODUCTION build (`next start`) with
// NEXT_PUBLIC_API_URL unset, so the app falls back to its bundled mock catalog.
// Static export is deliberately NOT used: `output: "export"` 500s every dynamic
// /markets/[slug] route (see next.config.ts), which would break the card-click
// test. `next start` serves the same production bundle dynamically.
const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: `npm run start -- --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: {
      // Ensure the mock fallback path: no real backend is contacted.
      NEXT_PUBLIC_API_URL: "",
      NEXT_PUBLIC_WS_URL: "",
    },
  },
});
