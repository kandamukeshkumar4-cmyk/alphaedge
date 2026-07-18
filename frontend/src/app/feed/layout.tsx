import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Feed",
  description: "Activity and signal feed for the paper-trading desk.",
  path: "/feed",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
