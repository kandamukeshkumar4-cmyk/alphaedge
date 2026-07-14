import type { Page } from "@playwright/test";

// Network-layer noise is expected while the app probes optional WS / poll
// endpoints. Keep React crashes and uncaught exceptions strict.
const NETWORK_NOISE =
  /Failed to load resource|net::ERR|ERR_FAILED|ERR_ABORTED|WebSocket connection to .* failed|favicon/i;

// BUG-V17-01 fixed (loop16 V7): no known app-bug console noise remains.
// Reintroduce a filter ONLY with a matching BUG REPORT (no silent skips).
const KNOWN_APP_BUG_NOISE = /$^/; // matches nothing

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
