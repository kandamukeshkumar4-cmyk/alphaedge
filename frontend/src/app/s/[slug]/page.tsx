import ShareSnapshotClient from "./share-client";
import { MARKETS } from "@/lib/mock-data";

// Z02 — Shareable snapshot page (backend M02,
// GET /api/v1/markets/{slug}/share-snapshot). Live Kalshi/Polymarket slugs are
// discovered at runtime and can't be enumerated ahead of time, so unknown slugs
// render on demand (dynamicParams). generateStaticParams still seeds the known
// catalog for prerender; the static-export demo deploy can only serve that set.
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
  return { title: `Snapshot · ${slug} | AlphaEdge` };
}

export default async function ShareSnapshotPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ShareSnapshotClient slug={slug} />;
}
