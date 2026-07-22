import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  return pageMetadata({
    title: "Scanner detail",
    description: `Scanner ${id} — pipeline canvas, latest run candidates and run history. Paper research only.`,
    path: `/scanners/${id}`,
  });
}

export default function ScannerDetailLayout({ children }: { children: React.ReactNode }) {
  return children;
}
