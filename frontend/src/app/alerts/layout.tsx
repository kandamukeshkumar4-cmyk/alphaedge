import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Alerts",
  description: "Signal alerts digest for paper research (notify/read only).",
  path: "/alerts",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
