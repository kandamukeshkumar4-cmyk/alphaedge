import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

/**
 * Loop 103 P2 — /screener SEO metadata.
 * Dense model-edge table. Read-only research. Paper trading only.
 */
export const metadata: Metadata = pageMetadata({
  title: "Screener",
  description:
    "Dense sortable table of paper markets ranked by model edge. Read-only research — simulated funds only.",
  path: "/screener",
});

export default function ScreenerLayout({ children }: { children: React.ReactNode }) {
  return children;
}
