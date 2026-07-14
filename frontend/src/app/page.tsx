import { Suspense } from "react";

import { QuestDiscoverShell } from "@/components/quest/QuestDiscoverShell";
import { QuestMobileRail } from "@/components/quest/QuestMobileRail";
import { QuestSignalRail } from "@/components/quest/QuestSignalRail";
import { fetchMarkets } from "@/lib/alphaedge-api";
import type { Market } from "@/lib/mock-data";

// Discover home — QuestFlow anatomy from the reference video:
// left live-signal rail + Traders Arena hero + Markets/Feed tabs + ATLAS rail.
export default async function DiscoverHome() {
  let initialMarkets: Market[] = [];
  try {
    initialMarkets = await fetchMarkets({ sort: "active" });
  } catch {
    // API unreachable at request time — client components will retry.
  }

  return (
    <div className="mx-auto max-w-[1600px] px-3 py-4 sm:px-4">
      <QuestMobileRail initialMarkets={initialMarkets} />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[232px_minmax(0,1fr)]">
        <div className="hidden lg:block">
          <div className="sticky top-[4.5rem] max-h-[calc(100vh-6rem)] overflow-y-auto pr-1">
            <QuestSignalRail initialMarkets={initialMarkets} />
          </div>
        </div>

        <main className="min-w-0">
          <Suspense fallback={<div className="skeleton mt-4 h-64 w-full rounded-xl" />}>
            <QuestDiscoverShell initialMarkets={initialMarkets} />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
