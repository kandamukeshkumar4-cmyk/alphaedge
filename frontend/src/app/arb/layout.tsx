import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Arb",
  description: "Paper arbitrage research board. Simulated funds only.",
  path: "/arb",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
