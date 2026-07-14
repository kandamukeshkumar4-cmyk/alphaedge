import type { Page } from "@playwright/test";

// Network-layer noise is expected while the app probes optional WS / poll
// endpoints. Keep React crashes and uncaught exceptions strict.
const NETWORK_NOISE =
  /Failed to load resource|net::ERR|ERR_FAILED|ERR_ABORTED|WebSocket connection to .* failed|favicon/i;

// Known app bugs filed under goals/loop-v17-e2e-qa/STATE.md BUG REPORTS.
// Do not expand this list without a matching BUG REPORT (no silent skips).
const KNOWN_APP_BUG_NOISE =
  /addColorStop.*could not be parsed as a color|rgba\(var\(--color-primary/i;

export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !NETWORK_NOISE.test(msg.text())) {
      errors.push(msg.text());
    }
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

export function assertNoConsoleErrors(errors: string[], path: string): void {
  const filtered = errors.filter(
    (e) => !NETWORK_NOISE.test(e) && !KNOWN_APP_BUG_NOISE.test(e),
  );
  if (filtered.length > 0) {
    throw new Error(`console errors on ${path}:\n${filtered.join("\n")}`);
  }
}
