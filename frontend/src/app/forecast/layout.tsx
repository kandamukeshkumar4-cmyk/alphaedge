import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Forecast",
  description: "Locked model forecasts and scoring overview. Not financial advice.",
  path: "/forecast",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
