import MarketDetailClient from "./market-detail-client";
import { getMarket, MARKETS } from "@/lib/mock-data";
import { fetchMarketDetailApi } from "@/lib/alphaedge-api";

export const dynamicParams = false;

export function generateStaticParams() {
  return MARKETS.map((m) => ({ slug: m.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const apiDetail = await fetchMarketDetailApi(slug);
  const localMarket = getMarket(slug);
  const title = apiDetail?.title ?? localMarket?.title ?? slug;
  return { title: `${title} | AlphaEdge` };
}

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <MarketDetailClient slug={slug} />;
}
