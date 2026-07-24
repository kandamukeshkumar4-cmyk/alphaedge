import { describe, expect, it } from "vitest";

import {
  absoluteUrl,
  DEFAULT_DESCRIPTION,
  pageMetadata,
  PUBLIC_SITEMAP_ROUTES,
  SITE_URL,
} from "./site-metadata";
import { PAPER_TRADING_DISCLAIMER } from "./paper-trading";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";

describe("site metadata (loop67 L2)", () => {
  it("builds absolute URLs against the public site origin", () => {
    expect(absoluteUrl("/")).toBe(SITE_URL);
    expect(absoluteUrl("/eval")).toBe(`${SITE_URL}/eval`);
  });

  it("emits per-route title, description, OG, and twitter cards", () => {
    const meta = pageMetadata({
      title: "Markets",
      description: "Browse open paper markets.",
      path: "/markets",
    });

    expect(meta.title).toBe("Markets");
    expect(meta.description).toBe("Browse open paper markets.");
    expect(meta.openGraph?.title).toBe("Markets — AlphaEdge");
    expect(meta.twitter).toMatchObject({ card: "summary_large_image" });
    expect(meta.alternates?.canonical).toBe(`${SITE_URL}/markets`);
  });

  it("keeps the exact paper-trading disclaimer as default description source", () => {
    expect(PAPER_TRADING_DISCLAIMER).toContain("paper-trading simulation");
    expect(PAPER_TRADING_DISCLAIMER).toContain("simulated funds");
    expect(DEFAULT_DESCRIPTION).toContain("simulated funds only");
    expect(DEFAULT_DESCRIPTION).toContain(PAPER_TRADING_DISCLAIMER);
  });

  it("lists loop103 launch routes in the public sitemap", () => {
    const paths = PUBLIC_SITEMAP_ROUTES.map((r) => r.path);
    for (const path of ["/terminal", "/scanners", "/skills", "/alpha", "/screener"]) {
      expect(paths).toContain(path);
    }
  });

  it("lists only public routes in the sitemap (no admin)", () => {
    const entries = sitemap();
    expect(entries.length).toBe(PUBLIC_SITEMAP_ROUTES.length);
    for (const entry of entries) {
      expect(entry.url).not.toContain("/admin");
      expect(entry.url.startsWith(SITE_URL)).toBe(true);
    }
    expect(PUBLIC_SITEMAP_ROUTES.some((r) => r.path === "/about")).toBe(true);
    expect(PUBLIC_SITEMAP_ROUTES.some((r) => r.path === "/terms")).toBe(true);
  });

  it("excludes auth login/signup from the public sitemap (loop71)", () => {
    expect(PUBLIC_SITEMAP_ROUTES.some((r) => r.path === "/auth/login")).toBe(false);
    expect(PUBLIC_SITEMAP_ROUTES.some((r) => r.path === "/auth/signup")).toBe(false);
    const urls = sitemap().map((e) => e.url);
    expect(urls.some((u) => u.includes("/auth/login"))).toBe(false);
    expect(urls.some((u) => u.includes("/auth/signup"))).toBe(false);
  });

  it("disallows admin in robots.txt and points at the sitemap", () => {
    const doc = robots();
    const rules = Array.isArray(doc.rules) ? doc.rules : [doc.rules];
    const disallow = rules.flatMap((r) => {
      const d = r?.disallow;
      if (!d) return [];
      return Array.isArray(d) ? d : [d];
    });
    expect(disallow.some((d) => String(d).includes("/admin"))).toBe(true);
    expect(doc.sitemap).toBe(`${SITE_URL}/sitemap.xml`);
  });
});
