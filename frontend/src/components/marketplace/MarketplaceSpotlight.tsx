"use client";

/**
 * Loop 98 (MU3) — Trending + Featured rows for /library.
 * Loads getTrendingMarketplace + getFeaturedMarketplace (live-first, mock
 * fallback). Horizontal rows above the library tabs. Skeletons + empty
 * states use reserved heights; motion respects reduced-motion kill-switch.
 * PAPER_TRADING_ONLY — browse-only, no order path.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { StarRating } from "@/components/marketplace/StarRating";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  getFeaturedMarketplace,
  getTrendingMarketplace,
  type FeaturedItem,
  type TrendingItem,
} from "@/lib/marketplace-api";

const SKELETON_COUNT = 4;
/** Reserved row height — skeleton + content share the same floor. */
const ROW_MIN_H = "min-h-[148px]";

function hrefFor(kind: "skill" | "scanner", id: string): string {
  return kind === "scanner" ? `/scanners/${id}` : "/skills";
}

function kindLabel(kind: "skill" | "scanner"): string {
  return kind === "scanner" ? "Scanner" : "Skill";
}

function RowSkeleton({ testId }: { testId: string }) {
  return (
    <ul
      data-testid={testId}
      aria-hidden="true"
      className={cn(
        "flex gap-3 overflow-hidden",
        ROW_MIN_H,
      )}
    >
      {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
        <li
          key={i}
          className="w-[220px] shrink-0 rounded-2xl border border-border bg-surface p-3"
        >
          <div className="t-skeleton h-8 w-8 rounded-lg" />
          <div className="t-skeleton mt-3 h-4 w-3/4 rounded" />
          <div className="t-skeleton mt-2 h-3 w-full rounded" />
          <div className="t-skeleton mt-4 h-5 w-24 rounded" />
        </li>
      ))}
    </ul>
  );
}

function EmptyRow({ testId, copy }: { testId: string; copy: string }) {
  return (
    <div
      data-testid={testId}
      className={cn(
        "flex items-center justify-center rounded-2xl border border-dashed border-border px-4 py-8 text-center",
        ROW_MIN_H,
      )}
    >
      <p className="max-w-sm text-sm text-muted">{copy}</p>
    </div>
  );
}

function SpotlightCard({
  item,
  showRating,
  index,
}: {
  item: TrendingItem | FeaturedItem;
  showRating: boolean;
  index: number;
}) {
  const stagger =
    index >= 1 && index <= 4 ? `t-stagger-${index}` : "";
  const trending = "trending_score" in item ? (item as TrendingItem) : null;
  return (
    <li
      data-testid="marketplace-spotlight-card"
      data-kind={item.kind}
      className={cn(
        "t-rise w-[220px] shrink-0 rounded-2xl border border-border bg-surface p-3 transition",
        "hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lift",
        "motion-reduce:transform-none motion-reduce:transition-none",
        stagger,
      )}
    >
      <Link
        href={hrefFor(item.kind, item.id)}
        className="block min-w-0"
      >
        <div className="flex items-start gap-2">
          <span
            aria-hidden
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary-dim/55 text-base"
          >
            {item.icon}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-bold tracking-tight text-text">
              {item.name}
            </p>
            <p className="mt-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-2">
              {kindLabel(item.kind)}
              {trending ? ` · score ${trending.trending_score.toFixed(1)}` : ""}
            </p>
          </div>
        </div>
        <p className="mt-2 line-clamp-2 min-h-[32px] text-[11px] leading-snug text-muted">
          {item.description || "No description."}
        </p>
      </Link>
      {showRating && trending ? (
        <div className="mt-2 min-h-[28px]">
          <StarRating
            kind={item.kind}
            id={item.id}
            name={item.name}
            initialAvg={trending.avg_rating}
            initialCount={trending.rating_count}
          />
        </div>
      ) : (
        <div className="mt-2 min-h-[28px]">
          <StarRating kind={item.kind} id={item.id} name={item.name} />
        </div>
      )}
    </li>
  );
}

export function MarketplaceSpotlight() {
  const { token, isReady } = useAuth();
  const [trending, setTrending] = useState<TrendingItem[]>([]);
  const [featured, setFeatured] = useState<FeaturedItem[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const tok = isReady ? token : null;
      const [t, f] = await Promise.all([
        getTrendingMarketplace(8, tok),
        getFeaturedMarketplace(tok),
      ]);
      setTrending(t.items);
      setFeatured(f.items);
    } finally {
      setLoading(false);
    }
  }, [isReady, token]);

  useEffect(() => {
    if (!isReady) return;
    void refresh();
  }, [isReady, refresh]);

  return (
    <div data-testid="marketplace-spotlight" className="mb-8 space-y-6">
      <section aria-labelledby="marketplace-trending-heading">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <h2
              id="marketplace-trending-heading"
              className="text-lg font-black tracking-tight text-text"
            >
              Trending
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              Ranked by recent runs and community ratings.
            </p>
          </div>
        </div>
        {loading ? (
          <RowSkeleton testId="marketplace-trending-skeleton" />
        ) : trending.length === 0 ? (
          <EmptyRow
            testId="marketplace-trending-empty"
            copy="Nothing trending yet — rate a skill or scanner to surface the board."
          />
        ) : (
          <ul
            data-testid="marketplace-trending-row"
            className={cn(
              "flex gap-3 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
              ROW_MIN_H,
            )}
          >
            {trending.map((item, i) => (
              <SpotlightCard
                key={`t-${item.kind}-${item.id}`}
                item={item}
                showRating
                index={i}
              />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="marketplace-featured-heading">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <h2
              id="marketplace-featured-heading"
              className="text-lg font-black tracking-tight text-text"
            >
              Featured
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              Editor picks from the skills and scanners catalog.
            </p>
          </div>
        </div>
        {loading ? (
          <RowSkeleton testId="marketplace-featured-skeleton" />
        ) : featured.length === 0 ? (
          <EmptyRow
            testId="marketplace-featured-empty"
            copy="No featured items yet — check back when the catalog highlights recipes."
          />
        ) : (
          <ul
            data-testid="marketplace-featured-row"
            className={cn(
              "flex gap-3 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
              ROW_MIN_H,
            )}
          >
            {featured.map((item, i) => (
              <SpotlightCard
                key={`f-${item.kind}-${item.id}`}
                item={item}
                showRating={false}
                index={i}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
