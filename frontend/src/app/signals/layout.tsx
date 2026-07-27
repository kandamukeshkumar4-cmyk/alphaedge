import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Signals",
  description: "Forecast-vs-market signal desk for paper research. No real-money execution.",
  path: "/signals",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
