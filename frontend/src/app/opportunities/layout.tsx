import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Opportunities",
  description: "Model-vs-market opportunity board for paper research.",
  path: "/opportunities",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
