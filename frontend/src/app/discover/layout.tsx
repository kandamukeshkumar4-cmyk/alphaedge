import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Discover",
  description: "Discover paper markets and signals. Simulated funds only.",
  path: "/discover",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
