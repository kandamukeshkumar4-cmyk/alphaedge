import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Markets",
  description: "Browse open paper markets across sports and elections. Simulated funds only.",
  path: "/markets",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
