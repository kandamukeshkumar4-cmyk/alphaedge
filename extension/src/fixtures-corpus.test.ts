import { describe, expect, it } from "vitest";

import corpus from "../fixtures/platform-pages.json";
import { parseSupportedUrl } from "./platforms";

type Fixture = {
  url: string;
  title: string;
  expectedExternalId: string;
  manualOnly: boolean;
  html: string;
};

describe("platform fixture corpus", () => {
  it.each(["polymarket", "kalshi", "fanduel"] as const)(
    "contains at least 20 saved URL/page fixtures for %s",
    (platform) => {
      expect(corpus[platform]).toHaveLength(20);
      for (const fixture of corpus[platform] as Fixture[]) {
        expect(fixture.html).toContain(fixture.title);
      }
    },
  );

  it.each(["polymarket", "kalshi"] as const)(
    "parses every %s fixture into the expected capture mode",
    (platform) => {
      for (const fixture of corpus[platform] as Fixture[]) {
        const parsed = parseSupportedUrl(fixture.url, fixture.title);
        expect(parsed, fixture.url).not.toBeNull();
        expect(parsed?.provider).toBe(platform);
        expect(parsed?.externalId).toBe(fixture.expectedExternalId);
        expect(parsed?.manualOnly).toBe(fixture.manualOnly);
        expect(parsed?.platform).toBe(platform);
      }
    },
  );

  it("FanDuel fixtures are deferred — parseSupportedUrl returns null for all fanduel URLs", () => {
    for (const fixture of corpus["fanduel"] as Fixture[]) {
      expect(parseSupportedUrl(fixture.url, fixture.title), fixture.url).toBeNull();
    }
  });
});
