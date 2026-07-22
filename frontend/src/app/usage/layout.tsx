import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Usage",
  description:
    "Paper research activity over the last 14 days — sessions, skill runs, scanner runs, and briefs. Simulated activity, paper trading only.",
  path: "/usage",
});

export default function UsageLayout({ children }: { children: React.ReactNode }) {
  return children;
}
