import { ScannerDetailShell } from "@/components/scanners/ScannerDetailShell";

export default async function ScannerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ScannerDetailShell id={id} />;
}
