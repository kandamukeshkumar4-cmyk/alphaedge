import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Skills",
  description:
    "One-tap research skills — each runs a full terminal session on the canonical paper market. Paper trading only.",
  path: "/skills",
});

export default function SkillsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
