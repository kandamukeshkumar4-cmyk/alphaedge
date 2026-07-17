import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Weather",
  description: "Weather market research views. Paper trading only.",
  path: "/weather",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
