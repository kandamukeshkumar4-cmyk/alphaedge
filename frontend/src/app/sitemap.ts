import type { MetadataRoute } from "next";

import { absoluteUrl, PUBLIC_SITEMAP_ROUTES } from "@/lib/site-metadata";

/**
 * Loop V67 (L2) — sitemap for public routes only (no /admin).
 *
 * force-static: the Azure SWA deploy builds with `output: "export"`, which
 * rejects metadata routes that are not statically renderable.
 */
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return PUBLIC_SITEMAP_ROUTES.map((route) => ({
    url: absoluteUrl(route.path),
    lastModified,
    changeFrequency: route.changeFrequency ?? "weekly",
    priority: route.priority ?? 0.5,
  }));
}
