import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Sign up",
  description: "Create an AlphaEdge paper-trading research account.",
  path: "/auth/signup",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
