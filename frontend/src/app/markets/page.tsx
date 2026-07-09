import { QuestLiveMarketsBoard } from "@/components/quest/QuestLiveMarketsBoard";
import { fetchMarkets } from "@/lib/alphaedge-api";
import type { Market } from "@/lib/mock-data";

export default async function MarketsPage() {
  let initialMarkets: Market[] = [];
  try {
    initialMarkets = await fetchMarkets({});
  } catch {
    // API unreachable at request time — client board keeps SSR payload on refetch failure.
  }

  return <QuestLiveMarketsBoard initialMarkets={initialMarkets} />;
}
