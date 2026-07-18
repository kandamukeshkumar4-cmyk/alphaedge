import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Watchlist",
  description: "Personal market watchlist for paper trading research.",
  path: "/watchlist",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
