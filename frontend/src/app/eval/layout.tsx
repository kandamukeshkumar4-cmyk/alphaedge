import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Proof",
  description: "Live evaluation and calibration proof — Brier, model registry, and honest unmeasured states.",
  path: "/eval",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
