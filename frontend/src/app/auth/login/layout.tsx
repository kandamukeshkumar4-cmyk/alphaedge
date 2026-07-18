import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Log in",
  description: "Log in to your AlphaEdge paper-trading account.",
  path: "/auth/login",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
