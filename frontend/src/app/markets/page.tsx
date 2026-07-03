import { Suspense } from "react";
import MarketsPageClient from "./markets-client";

export default function MarketsPage() {
  return (
    <Suspense fallback={<div className="py-12 text-center text-white/40">Loading…</div>}>
      <MarketsPageClient />
    </Suspense>
  );
}
