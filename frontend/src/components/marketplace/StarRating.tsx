"use client";

/**
 * Loop 98 (MU2) — reusable 5-star rating widget for skill + scanner cards.
 * Hover preview, click POSTs via marketplace-api.rate, then shows avg + count
 * + my rating. Mint (primary) stars only — never danger-red.
 * Reserved height keeps card layout stable while ratings hydrate / update.
 * PAPER_TRADING_ONLY — rating never touches the order path.
 */

import { useEffect, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  rate,
  type MarketplaceKind,
  type RatingOut,
} from "@/lib/marketplace-api";

const STAR_COUNT = 5;

function StarIcon({
  filled,
  preview,
}: {
  filled: boolean;
  preview: boolean;
}) {
  const active = filled || preview;
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={cn(
        "transition-colors duration-150 motion-reduce:transition-none",
        active ? "text-primary" : "text-muted-2/55",
        preview && !filled ? "text-primary/70" : null,
      )}
    >
      <path
        d="M12 2.8l2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 16.7 6.6 19.6l1-6.1L3.2 9.2l6.1-.9L12 2.8z"
        fill={active ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function StarRating({
  kind,
  id,
  name,
  initialAvg = 0,
  initialCount = 0,
  initialMyStars = 0,
  className,
}: {
  kind: MarketplaceKind;
  id: string;
  name?: string;
  initialAvg?: number;
  initialCount?: number;
  initialMyStars?: number;
  className?: string;
}) {
  const { token, isReady } = useAuth();
  const [rating, setRating] = useState<RatingOut>({
    avg: initialAvg,
    count: initialCount,
    my_stars: initialMyStars,
  });
  const [hover, setHover] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRating({
      avg: initialAvg,
      count: initialCount,
      my_stars: initialMyStars,
    });
  }, [id, initialAvg, initialCount, initialMyStars]);

  const displayValue = hover > 0 ? hover : rating.my_stars || 0;
  const avgLabel =
    rating.count > 0 ? rating.avg.toFixed(rating.avg % 1 === 0 ? 0 : 1) : "—";

  async function onRate(stars: number) {
    if (busy || !isReady) return;
    setBusy(true);
    setError(null);
    try {
      const { rating: next } = await rate(kind, id, stars, token);
      setRating(next);
    } catch {
      setError("Could not save rating");
    } finally {
      setBusy(false);
      setHover(0);
    }
  }

  const labelBase = name ? `${name} ` : "";

  return (
    <div
      data-testid="star-rating"
      data-kind={kind}
      data-id={id}
      className={cn(
        "flex min-h-[28px] items-center gap-2",
        className,
      )}
    >
      <div
        role="radiogroup"
        aria-label={`Rate ${labelBase}${kind}`.trim()}
        className="flex items-center gap-0.5"
        onMouseLeave={() => setHover(0)}
      >
        {Array.from({ length: STAR_COUNT }, (_, i) => {
          const stars = i + 1;
          const filled = stars <= (rating.my_stars || 0);
          const preview = hover > 0 && stars <= hover;
          return (
            <button
              key={stars}
              type="button"
              role="radio"
              aria-checked={rating.my_stars === stars}
              aria-label={`${stars} star${stars === 1 ? "" : "s"}`}
              data-testid={`star-${stars}`}
              disabled={busy || !isReady}
              onMouseEnter={() => setHover(stars)}
              onFocus={() => setHover(stars)}
              onBlur={() => setHover(0)}
              onClick={() => void onRate(stars)}
              className={cn(
                "grid h-6 w-6 place-items-center rounded-md transition",
                "hover:bg-primary-dim/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35",
                "disabled:cursor-wait disabled:opacity-60",
                "motion-reduce:transition-none",
              )}
            >
              <StarIcon filled={filled} preview={preview} />
            </button>
          );
        })}
      </div>

      <p
        data-testid="star-rating-meta"
        className="min-w-0 truncate font-mono text-[10px] tabular-nums text-muted"
        title={
          rating.my_stars > 0
            ? `Average ${avgLabel} · ${rating.count} ratings · yours ${rating.my_stars}`
            : `Average ${avgLabel} · ${rating.count} ratings`
        }
      >
        <span className="font-bold text-text">{avgLabel}</span>
        <span className="text-muted-2"> · {rating.count}</span>
        {rating.my_stars > 0 ? (
          <span className="text-primary"> · you {rating.my_stars}</span>
        ) : displayValue > 0 && hover > 0 ? (
          <span className="text-muted-2"> · rate {displayValue}</span>
        ) : null}
      </p>

      {error ? (
        <span className="sr-only" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
