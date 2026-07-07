import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: {
    jsx: {
      runtime: "automatic",
      importSource: "react",
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "node",
    // Unit tests live under src/. Exclude e2e/ so Playwright specs (which use
    // @playwright/test, not vitest) are not collected by `vitest run`.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
