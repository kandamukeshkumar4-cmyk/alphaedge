import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Research Terminal",
  description:
    "AI research terminal: streamed steps, confluence scoreboard, paper trading only.",
  path: "/terminal",
});

export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  return children;
}
