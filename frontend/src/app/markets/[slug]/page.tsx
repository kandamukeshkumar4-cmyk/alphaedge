import MarketDetailClient from "./market-detail-client";
import { MARKETS } from "@/lib/mock-data";

export const dynamicParams = false;

export function generateStaticParams() {
  return MARKETS.map((m) => ({ slug: m.slug }));
}

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <MarketDetailClient slug={slug} />;
}
