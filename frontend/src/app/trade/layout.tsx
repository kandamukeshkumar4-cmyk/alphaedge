import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Trade",
  description: "Paper trade prediction markets with simulated funds. Research and portfolio demonstration only.",
  path: "/trade",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
