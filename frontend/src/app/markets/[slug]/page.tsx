import MarketDetailClient from "./market-detail-client";
import { getMarket, MARKETS } from "@/lib/mock-data";
import { fetchMarketDetail, fetchMarketDetailApi } from "@/lib/alphaedge-api";
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
  // SSR-fetch the live detail AND the live catalog row so the first paint is
  // the real market.
  //
  // Loop117 (D14): the server used to fetch only `/detail`, while the "Showing
  // demo market data. Connect the API…" banner and the fabricated sample order
  // book keyed off the API-backed market, which was client-only state. Every
  // server render therefore claimed the API was disconnected and shipped a
  // synthetic book — what crawlers, no-JS clients and the first paint saw —
  // even though the API was up and serving an empty book.
  const [initialDetail, initialMarket] = await Promise.all([
    fetchMarketDetailApi(slug),
    fetchMarketDetail(slug),
  ]);
  return (
    <MarketDetailClient
      slug={slug}
      initialDetail={initialDetail}
      initialMarket={initialMarket}
    />
  );
}
