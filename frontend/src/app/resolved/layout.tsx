import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Resolved",
  description: "Resolved paper markets and graded outcomes.",
  path: "/resolved",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
