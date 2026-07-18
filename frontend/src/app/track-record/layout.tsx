import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Track record",
  description: "Historical paper track record and reliability views from resolved markets.",
  path: "/track-record",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
