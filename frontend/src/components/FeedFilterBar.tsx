"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/cn";
import type { FeedItemType } from "@/lib/feed-api";

const TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All" },
  { value: "alignment", label: "Alignment" },
  { value: "whale_delta", label: "Whale" },
  { value: "news_arrival", label: "News" },
  { value: "instability_shift", label: "Instability" },
  { value: "signal", label: "Signals" },
  { value: "brief", label: "Brief" },
  { value: "digest", label: "Digest" },
  { value: "claim_graded", label: "Graded" },
];

const PLATFORM_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All platforms" },
  { value: "polymarket", label: "Polymarket" },
  { value: "kalshi", label: "Kalshi" },
];

interface FeedFilterBarProps {
  activeType: string;
  activePlatform: string;
}

export function FeedFilterBar({ activeType, activePlatform }: FeedFilterBarProps) {
  const router = useRouter();
  const params = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    // Reset offset on filter change
    next.delete("offset");
    router.push(`/feed?${next.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Type pills */}
      <div className="flex flex-wrap items-center gap-1">
        {TYPE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => update("type", opt.value)}
            className={cn(
              "rounded-md px-2.5 py-1 text-[11px] font-semibold transition",
              activeType === opt.value
                ? "bg-accent-bright text-bg"
                : "bg-surface text-muted hover:bg-surface-2 hover:text-text",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Platform select */}
      <select
        value={activePlatform}
        onChange={(e) => update("platform", e.target.value)}
        className="ml-auto rounded-md border border-border bg-surface px-2 py-1 text-[11px] text-muted hover:border-border-light focus:outline-none"
      >
        {PLATFORM_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
