import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site-metadata";

/**
 * Loop V67 (L2) — robots.txt for public launch.
 * Public routes allowed; admin (and related private tooling) disallowed.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin", "/admin/", "/api/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
