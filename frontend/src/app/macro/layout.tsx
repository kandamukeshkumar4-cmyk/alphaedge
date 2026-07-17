import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Macro",
  description: "Macro market research views. Paper trading only.",
  path: "/macro",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
