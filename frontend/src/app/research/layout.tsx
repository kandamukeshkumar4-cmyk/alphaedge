import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Research",
  description: "Desk research briefs and market intelligence. Paper trading only.",
  path: "/research",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
