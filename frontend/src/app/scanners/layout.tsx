import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Scanner Studio",
  description:
    "Describe a scanner in plain English, compile it into a scheduled alert spec, and run it on paper. Research only — no orders.",
  path: "/scanners",
});

export default function ScannersLayout({ children }: { children: React.ReactNode }) {
  return children;
}
