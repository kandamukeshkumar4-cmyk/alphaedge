import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Home",
  description: "AlphaEdge paper-trading home. Simulated funds for research only.",
  path: "/home",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
