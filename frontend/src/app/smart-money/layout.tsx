import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Smart money",
  description: "Smart-money research views for paper markets.",
  path: "/smart-money",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
