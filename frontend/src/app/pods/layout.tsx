import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Pods",
  description: "Research pods with paper equity and decision logs. Simulated funds only.",
  path: "/pods",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
