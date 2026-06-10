"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchMarkets, toApiCategory } from "@/lib/alphaedge-api";
import type { Market } from "@/lib/mock-data";
import { formatCompactUSD, pct } from "@/lib/mock-data";

type Props = {
  currentSlug: string;
  category: string;
};

export function SimilarMarkets({ currentSlug, category }: Props) {
  const [markets, setMarkets] = useState<Market[]>([]);

  useEffect(() => {
    let cancelled = false;

    const categoryParam = toApiCategory(category);
    if (!categoryParam) {
      setMarkets([]);
      return;
    }

    fetchMarkets({ category: categoryParam, sort: "volume" })
      .then((all) => {
        if (cancelled) return;
        const similar = all
          .filter((m) => m.slug !== currentSlug)
          .slice(0, 3);
        setMarkets(similar);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [currentSlug, category]);

  if (!markets.length) return null;

  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <h3 className="mb-3 text-sm font-black text-text">Similar Markets</h3>
      <ul className="space-y-2">
        {markets.map((m) => {
          const primary = m.outcomes[0];
          return (
            <li key={m.slug}>
              <Link
                href={`/markets/${m.slug}`}
                className="flex items-center justify-between gap-3 rounded-xl p-2 transition hover:bg-surface-2"
              >
                <span className="flex items-center gap-2 min-w-0">
                  <span className="text-base">{m.icon}</span>
                  <span className="truncate text-xs font-semibold text-text">{m.title}</span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block text-xs font-mono font-bold text-primary">
                    {pct(primary?.price ?? 0)}
                  </span>
                  <span className="block text-[10px] text-muted">
                    {formatCompactUSD(m.volume)} vol
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
