import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Compare",
  description: "Side-by-side market intelligence comparison. Paper trading only.",
  path: "/compare",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
