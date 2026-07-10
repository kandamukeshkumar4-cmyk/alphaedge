"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useWatchlist } from "@/hooks/useWatchlist";
import { cn } from "@/lib/cn";

/**
 * W01 — star/☆ toggle. Optimistic via useWatchlist; when anon (no JWT) it routes
 * to sign-in instead of persisting. This is a watchlist bookmark, never an order.
 */
export function WatchlistStar({
  slug,
  size = "md",
  className,
}: {
  slug: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const router = useRouter();
  const { isWatched, toggle } = useWatchlist();
  const [busy, setBusy] = useState(false);
  const watched = isWatched(slug);

  const onClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    const result = await toggle(slug);
    setBusy(false);
    if (result === "anon") {
      router.push("/auth/login?next=/watchlist");
    }
  };

  const box = size === "sm" ? "h-7 w-7" : "h-8 w-8";

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={watched}
      aria-label={watched ? `Remove ${slug} from watchlist` : `Add ${slug} to watchlist`}
      title={watched ? "Tracking — click to remove" : "Track this market"}
      className={cn(
        "grid shrink-0 place-items-center rounded-lg border transition",
        box,
        watched
          ? "border-primary/40 bg-primary-dim text-primary"
          : "border-border text-muted hover:border-border-light hover:text-text",
        className,
      )}
    >
      <StarIcon filled={watched} />
    </button>
  );
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  );
}
