/**
 * Legacy stub-based suite retired by Loop V17.
 * Journeys now live in smoke.spec.ts / discover.spec.ts / trade.spec.ts /
 * coverage.spec.ts and run against real local uvicorn + next dev.
 *
 * This file intentionally has no tests so Playwright does not pick up the
 * old mock-abort routes against the live stack.
 */

import { test } from "@playwright/test";

test.describe.skip("legacy mock-stub suite (retired by loop17)", () => {
  test("placeholder", () => {
    /* no-op */
  });
});
