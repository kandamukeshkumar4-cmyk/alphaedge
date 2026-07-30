import type { MetadataRoute } from "next";

/**
 * Loop 103 P1 — Web App Manifest for installability.
 *
 * Icons: references the existing App Router icon at `/icon.svg`
 * (`frontend/src/app/icon.svg`). No fabricated PNG binaries.
 * Dedicated maskable PNGs (192×192 / 512×512) should be generated from
 * that SVG when a design pass produces them; until then SVG `any` is the
 * honest install icon.
 */
// Required for `output: export` builds (Azure SWA): the manifest route must
// be statically generated or the export build fails collecting page data.
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AlphaEdge",
    short_name: "AlphaEdge",
    description:
      "AI research desk for paper prediction-market trading — simulated funds only",
    start_url: "/",
    display: "standalone",
    background_color: "#070B0A",
    theme_color: "#00E8B0",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
