import { describe, expect, it } from "vitest";
import { marketHref, marketIntelHref, briefHref } from "./market-href";

// The canonical seed market is prebuilt as a static /markets/[slug] page.
const STATIC_SLUG = "nba-2025-01-15-lal-bos";
// Live mirrored slugs (pm-*/ks-*) are not in the seed catalog → query routes.
const LIVE_SLUG = "pm-live-market-123";

describe("marketHref", () => {
  it("routes a static seed slug to the prebuilt path", () => {
    expect(marketHref(STATIC_SLUG)).toBe(`/markets/${STATIC_SLUG}`);
  });

  it("appends query params to a static slug path", () => {
    expect(marketHref(STATIC_SLUG, { side: "yes" })).toBe(
      `/markets/${STATIC_SLUG}?side=yes`,
    );
  });

  it("routes a live slug through the query-param view route", () => {
    expect(marketHref(LIVE_SLUG)).toBe(
      `/markets/view?slug=${encodeURIComponent(LIVE_SLUG)}`,
    );
  });

  it("carries extra params alongside the live slug", () => {
    const href = marketHref(LIVE_SLUG, { side: "no" });
    expect(href.startsWith("/markets/view?")).toBe(true);
    const params = new URLSearchParams(href.split("?")[1]);
    expect(params.get("slug")).toBe(LIVE_SLUG);
    expect(params.get("side")).toBe("no");
  });
});

describe("marketIntelHref", () => {
  it("anchors the intelligence panel on a static slug", () => {
    expect(marketIntelHref(STATIC_SLUG)).toBe(
      `/markets/${STATIC_SLUG}#intelligence`,
    );
  });

  it("anchors the intelligence panel on a live view route", () => {
    expect(marketIntelHref(LIVE_SLUG)).toBe(
      `/markets/view?slug=${encodeURIComponent(LIVE_SLUG)}#intelligence`,
    );
  });
});

describe("briefHref", () => {
  it("uses the prebuilt brief page for a static slug", () => {
    expect(briefHref(STATIC_SLUG)).toBe(`/research/brief/${STATIC_SLUG}`);
  });

  it("uses the query-param brief route for a live slug", () => {
    expect(briefHref(LIVE_SLUG)).toBe(
      `/research/brief?slug=${encodeURIComponent(LIVE_SLUG)}`,
    );
  });
});
