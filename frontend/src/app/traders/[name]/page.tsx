import { TraderDetail } from "@/components/traders/TraderDetail";

export default async function TraderProfilePage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  return <TraderDetail name={decodeURIComponent(name)} />;
}
