import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

/**
 * Loop 103 P2 — /alpha SEO metadata.
 * Read-only multi-factor research. Paper trading only.
 */
export const metadata: Metadata = pageMetadata({
  title: "Multi-Factor Alpha",
  description:
    "Paper-only factor research: seven signals scored per market, shown as edge only when they beat the closing line out-of-sample. Simulated funds only.",
  path: "/alpha",
});

export default function AlphaLayout({ children }: { children: React.ReactNode }) {
  return children;
}
