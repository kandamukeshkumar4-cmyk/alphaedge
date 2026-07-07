"use client";

import { useEffect, useState } from "react";

import { MarketCard, MarketCardSkeleton } from "@/components/MarketCard";
import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { MARKETS as MOCK_MARKETS } from "@/lib/mock-data";
import {
  fetchMarkets,
  type Market,
  type MarketCategory,
} from "@/lib/markets-api";
import { Chip, PageHeader, PageShell, SegTabs, StatRow, StatTile } from "@/components/ui/kit";

const CATEGORY_MAP: Record<string, string> = {
  Sports: "NBA",
  Politics: "Elections",
  Crypto: "Crypto",
  Culture: "Culture",
  Economics: "Economics",
};

// Demo markets (markets-api shape) derived from the shared mock catalog so the
// grid renders in demo mode, consistent with the rest of the app.
const DEMO_MARKETS: Market[] = MOCK_MARKETS.map((m) => ({
  id: m.id,
  slug: m.slug,
  title: m.title,
  platform: m.seed % 2 === 0 ? "Polymarket" : "Kalshi",
  status: "open",
  implied_yes: m.outcomes[0]?.price ?? null,
  category: CATEGORY_MAP[m.category] ?? m.category,
  resolution_outcome: null,
}));

type StatusFilter = "all" | "open" | "resolved";
type CategoryFilter = "all" | MarketCategory;

const CATEGORY_TABS: { label: string; value: CategoryFilter }[] = [
  { label: "All", value: "all" },
  { label: "NBA", value: "NBA" },
  { label: "FIFA WC2026", value: "FIFA WC2026" },
  { label: "Elections", value: "Elections" },
  { label: "Crypto", value: "Crypto" },
  { label: "Culture", value: "Culture" },
  { label: "Economics", value: "Economics" },
];

const STATUS_OPTIONS = [
  { label: "All", value: "all" as const },
  { label: "Open", value: "open" as const },
  { label: "Resolved", value: "resolved" as const },
];

const PLATFORMS = ["all", "Polymarket", "Kalshi"] as const;
type PlatformFilter = (typeof PLATFORMS)[number];

export default function MarketsPage() {
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [platform, setPlatform] = useState<PlatformFilter>("all");
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const apiConfigured = Boolean(API_BASE);

  useEffect(() => {
    if (!apiConfigured) {
      const filtered = DEMO_MARKETS.filter((m) => {
        const catOk = category === "all" || m.category === category;
        const statusOk =
          filter === "all" ||
          (filter === "open" ? m.status !== "resolved" : m.status === "resolved");
        return catOk && statusOk;
      });
      setMarkets(filtered);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const apiFilter = filter === "all" ? undefined : filter;
        const apiCategory = category === "all" ? undefined : category;
        const next = await fetchMarkets(apiFilter, apiCategory);
        if (!cancelled) {
          setMarkets(next);
        }
      } catch (loadError) {
        if (!cancelled) {
          setMarkets([]);
          setError(
            loadError instanceof Error ? loadError.message : "Failed to load markets.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [apiConfigured, category, filter]);

  const emptyLabel =
    category === "all"
      ? filter === "all"
        ? ""
        : `${filter} `
      : filter === "all"
        ? `${category} `
        : `${category} ${filter} `;

  const visible =
    platform === "all" ? markets : markets.filter((m) => m.platform === platform);
  const openCount = visible.filter((m) => m.status !== "resolved").length;
  const avgYes =
    visible.length > 0
      ? Math.round(
          (visible.reduce((sum, m) => sum + (m.implied_yes ?? 0), 0) / visible.length) * 100,
        )
      : 0;

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Market discovery"
        title="Markets"
        subtitle="Browse open and resolved prediction markets across Polymarket and Kalshi with implied YES pricing and an AI edge on every card."
        actions={<SegTabs value={filter} onChange={setFilter} options={STATUS_OPTIONS} size="sm" />}
      />

      <div className="no-scrollbar mb-4 flex gap-2 overflow-x-auto">
        {PLATFORMS.map((p) => (
          <Chip key={p} active={platform === p} onClick={() => setPlatform(p)}>
            <span className="inline-flex items-center gap-1.5">
              {p !== "all" ? (
                <span
                  className={cn(
                    "inline-block h-2 w-2 rounded-full",
                    p === "Polymarket" ? "bg-secondary" : "bg-primary",
                  )}
                />
              ) : null}
              {p === "all" ? "All platforms" : p}
            </span>
          </Chip>
        ))}
      </div>

      <StatRow cols={3} className="mb-6">
        <StatTile label="Markets" value={visible.length.toLocaleString()} />
        <StatTile label="Open now" value={openCount.toLocaleString()} deltaTone="up" delta="live" accent />
        <StatTile label="Avg implied YES" value={`${avgYes}%`} />
      </StatRow>

      <div className="no-scrollbar mb-6 flex flex-wrap gap-2">
        {CATEGORY_TABS.map((item) => (
          <Chip
            key={item.value}
            active={category === item.value}
            onClick={() => setCategory(item.value)}
          >
            {item.label}
          </Chip>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <MarketCardSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-10 text-center text-sm text-danger">
          {error}
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          No {emptyLabel}markets found.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((market) => (
            <MarketCard key={market.id} market={market} />
          ))}
        </div>
      )}
    </PageShell>
  );
}
