import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Mirror",
  description: "Forecast mirror research view. Paper trading only.",
  path: "/mirror",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
