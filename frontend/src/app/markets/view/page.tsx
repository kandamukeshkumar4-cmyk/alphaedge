"use client";

// Detail route for live mirrored markets (dynamic slugs that can't be
// statically exported): /markets/view?slug=pm-...
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import MarketDetailClient from "../[slug]/market-detail-client";

function MarketViewInner() {
  const searchParams = useSearchParams();
  const slug = searchParams.get("slug");

  if (!slug) {
    return (
      <main className="mx-auto max-w-[800px] px-4 py-16 text-center sm:px-6">
        <p className="text-lg font-semibold text-text">Market not found</p>
        <Link
          href="/markets"
          className="mt-5 inline-block rounded-pill bg-accent px-5 py-2 text-sm font-semibold text-bg hover:bg-accent-active"
        >
          Browse markets
        </Link>
      </main>
    );
  }

  return <MarketDetailClient slug={slug} />;
}

export default function MarketViewPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-[1100px] px-4 py-8 sm:px-6">
          <div className="h-96 animate-pulse rounded-2xl border border-border bg-surface" />
        </main>
      }
    >
      <MarketViewInner />
    </Suspense>
  );
}
