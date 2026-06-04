import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import manifest from "../public/manifest.json";
import { findForbiddenCapabilities } from "./safety";

const EXTENSION_ROOT = fileURLToPath(new URL("..", import.meta.url));

describe("MV3 manifest and safety contract", () => {
  it("uses narrow permissions and host permissions only", () => {
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.permissions.sort()).toEqual(["storage"].sort());
    expect(manifest.host_permissions.sort()).toEqual(
      [
        "https://polymarket.com/*",
        "https://*.polymarket.com/*",
        "https://kalshi.com/*",
        "https://*.kalshi.com/*",
        "https://sportsbook.fanduel.com/*",
        "https://*.alphaedge.local/*",
        "http://localhost:8000/*",
        "https://*.azurestaticapps.net/*",
        "https://*.vercel.app/*",
      ].sort(),
    );
    expect(JSON.stringify(manifest)).not.toContain("<all_urls>");
    expect(JSON.stringify(manifest)).not.toContain("webRequest");
    expect(JSON.stringify(manifest)).not.toContain("tabs");
  });

  it("contains no betting execution, wallet, private-key, payment, or account scraping paths", () => {
    const source = [
      readFileSync(join(EXTENSION_ROOT, "src", "platforms.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "messaging.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "queue.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "receipt.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "storage.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "lifecycle.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "content", "overlay.tsx"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "background.ts"), "utf8"),
      readFileSync(join(EXTENSION_ROOT, "src", "popup", "Popup.tsx"), "utf8"),
      JSON.stringify(manifest),
    ].join("\n");

    expect(findForbiddenCapabilities(source)).toEqual([]);
  });
});
