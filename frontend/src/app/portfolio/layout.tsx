import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Portfolio",
  description: "Simulated portfolio, positions, and paper P&L. Research demonstration only.",
  path: "/portfolio",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
