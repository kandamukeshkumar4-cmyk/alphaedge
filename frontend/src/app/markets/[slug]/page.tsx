import MarketDetailClient from "./market-detail-client";
import { getMarket, MARKETS } from "@/lib/mock-data";
import { fetchMarketDetailApi } from "@/lib/alphaedge-api";

// Live Kalshi/Polymarket slugs are discovered at runtime and can't be
// enumerated ahead of time — they must render dynamically. The static list
// below only seeds prerendering for the static-export demo deploy.
// Live catalog slugs render on demand in server mode, but "output: export"
// (Azure SWA static deploy) forbids dynamicParams — unknown slugs 404 there.
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
