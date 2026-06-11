import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const BANNED = [
  "place bet",
  "auto bet",
  "guaranteed profit",
  "wallet",
  "private key",
  "real-money",
];

const FILES = [
  "src/app/mirror/page.tsx",
  "src/app/forecast/page.tsx",
  "src/lib/forecast-mirror-api.ts",
  "src/lib/forecast-dashboard-view-model.ts",
];

describe("mirror UI copy safety", () => {
  for (const file of FILES) {
    it(`${file} contains no betting-execution copy or credential fields`, () => {
      const source = readFileSync(path.resolve(__dirname, "../..", file), "utf8").toLowerCase();
      for (const phrase of BANNED) {
        expect(source.includes(phrase), `banned phrase "${phrase}" in ${file}`).toBe(false);
      }
      expect(source.includes('type="password"')).toBe(false);
      expect(source.includes("privatekey")).toBe(false);
    });
  }
});
