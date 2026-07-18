import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Leaderboard",
  description: "Paper-trading leaderboard of simulated portfolio performance.",
  path: "/leaderboard",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
