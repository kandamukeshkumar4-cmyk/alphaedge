import { SharedWatchlist } from "@/components/community/SharedWatchlist";

export const dynamicParams = true;

export function generateStaticParams() {
  return [{ handle: "demo" }];
}

export default async function SharedWatchlistPage({
  params,
}: {
  params: Promise<{ handle: string }>;
}) {
  const { handle } = await params;
  return <SharedWatchlist handle={handle} />;
}
