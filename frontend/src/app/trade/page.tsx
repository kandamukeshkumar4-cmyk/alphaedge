"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { TradeTerminal } from "@/components/quest/TradeTerminal";

function TradeInner() {
  const searchParams = useSearchParams();
  const slug = searchParams.get("slug") ?? undefined;
  return <TradeTerminal initialSlug={slug} />;
}

export default function TradePage() {
  return (
    <Suspense fallback={<div className="skeleton m-4 h-[70vh] rounded-xl" />}>
      <TradeInner />
    </Suspense>
  );
}
