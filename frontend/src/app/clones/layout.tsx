import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Clones",
  description: "Clone research strategies as paper portfolios.",
  path: "/clones",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
