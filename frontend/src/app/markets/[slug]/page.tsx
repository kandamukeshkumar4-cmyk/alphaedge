import MarketDetailClient from "./market-detail-client";
import { getMarket, MARKETS } from "@/lib/mock-data";
import { fetchMarketDetailApi } from "@/lib/alphaedge-api";
import { formatMarketLabel } from "@/lib/signals-dashboard-view-model";

// Live Kalshi/Polymarket slugs are discovered at runtime and can't be
// enumerated ahead of time — they must render dynamically. The static list
// below only seeds prerendering for the static-export demo deploy.
// Live catalog slugs render on demand in server mode, but "output: export"
// (Azure SWA static deploy) forbids dynamicParams — unknown slugs 404 there.
// Live catalog slugs are discovered at runtime, so they must render on demand.
// Next requires this to be a static literal, so it stays `true` for the Vercel
// server deploy (the live path). The retired static-export build cannot serve
// unknown slugs regardless; generateStaticParams still seeds the known set.
export const dynamicParams = true;

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
  const title = apiDetail?.title ?? localMarket?.title ?? formatMarketLabel(slug);
  return { title: `${title} | AlphaEdge` };
}

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  // SSR-fetch the live detail so the market question (not the raw slug) is in
  // the first paint for pm-/ks- slugs; the client still refreshes it.
  const initialDetail = await fetchMarketDetailApi(slug);
  return <MarketDetailClient slug={slug} initialDetail={initialDetail} />;
}
