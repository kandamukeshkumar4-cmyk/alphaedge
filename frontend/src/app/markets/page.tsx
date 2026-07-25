import { QuestLiveMarketsBoard } from "@/components/quest/QuestLiveMarketsBoard";
import { fetchMarketsPage } from "@/lib/alphaedge-api";
import type { Market } from "@/lib/mock-data";

const PAGE_LIMIT = 100;

export default async function MarketsPage() {
  let initialMarkets: Market[] = [];
  let initialTotal = 0;
  try {
    const page = await fetchMarketsPage({ sort: "active", limit: PAGE_LIMIT, offset: 0 });
    initialMarkets = page.items;
    initialTotal = page.total;
  } catch {
    // API unreachable at request time — client board keeps SSR payload on refetch failure.
  }

  return (
    <QuestLiveMarketsBoard initialMarkets={initialMarkets} initialTotal={initialTotal} />
  );
}
