"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useAtlasPanel } from "@/context/atlas-panel";
import { fetchMarketsPage, hasLiveApi } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { formatCompactUSD, MARKETS, type Market } from "@/lib/mock-data";
import { marketHref, marketIntelHref } from "@/lib/market-href";
import { activeTrendingMarkets } from "@/lib/live-discovery";
import { marketLifecycle } from "@/lib/market-lifecycle";

const FETCH_MS = 8000;
const PAGE_LIMIT = 100;
const LIVE_API = hasLiveApi();

type MarketLoadResult = {
  markets: Market[];
  fetched: number;
  total: number;
  source: "live" | "seed";
};

async function loadMarketsOrFallback(offset = 0): Promise<MarketLoadResult> {
  try {
    const page = await Promise.race([
      fetchMarketsPage({ sort: "active", limit: PAGE_LIMIT, offset }),
      new Promise<never>((_, reject) => {
        window.setTimeout(() => reject(new Error("markets-timeout")), FETCH_MS);
      }),
    ]);
    const rows = page.items;
    const fetched = rows.length;
    const active = activeTrendingMarkets(rows);
    const live = active.filter((m) => m.slug.startsWith("pm-") || m.slug.startsWith("ks-"));
    if (live.length > 0) {
      return { markets: live, fetched, total: page.total, source: "live" };
    }
    if (active.length > 0) {
      return { markets: active, fetched, total: page.total, source: "live" };
    }
    // Only fall back to bundled seed catalog when the live API is unavailable.
    if (LIVE_API) return { markets: [], fetched, total: page.total, source: "live" };
    return {
      markets: MARKETS,
      fetched: MARKETS.length,
      total: MARKETS.length,
      source: "seed",
    };
  } catch {
    return LIVE_API
      ? { markets: [], fetched: 0, total: 0, source: "live" }
      : {
          markets: MARKETS,
          fetched: MARKETS.length,
          total: MARKETS.length,
          source: "seed",
        };
  }
}

const PLATFORMS = ["Polymarket", "Kalshi", "All"] as const;
const CATS = ["All", "Sports", "Politics", "Crypto", "Culture", "Economics"] as const;

const SPORT_SIDEBAR = [
  { id: "live", label: "Live" },
  { id: "nba", label: "Basketball" },
  { id: "mlb", label: "Baseball" },
  { id: "soccer", label: "Soccer" },
  { id: "ufc", label: "UFC" },
  { id: "tennis", label: "Tennis" },
  { id: "football", label: "Football" },
];

function isLiveish(m: Market): boolean {
  const t = `${m.title} ${m.category}`.toLowerCase();
  return m.category === "Sports" || t.includes("vs") || t.includes(" vs.");
}

function splitTeams(title: string): [string, string] | null {
  const parts = title.split(/\s+vs\.?\s+/i);
  if (parts.length === 2) return [parts[0].trim(), parts[1].trim()];
  return null;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

export function QuestLiveMarketsBoard({
  initialMarkets,
  initialTotal = 0,
}: {
  initialMarkets?: Market[];
  initialTotal?: number;
}) {
  const { openPanel } = useAtlasPanel();
  const [markets, setMarkets] = useState<Market[]>(initialMarkets ?? []);
  const [total, setTotal] = useState(
    initialTotal > 0 ? initialTotal : (initialMarkets?.length ?? 0),
  );
  const [loadedCount, setLoadedCount] = useState(initialMarkets?.length ?? 0);
  const [seedFallback, setSeedFallback] = useState(
    Boolean(initialMarkets?.some((market) => market.source === "seed")),
  );
  const [loading, setLoading] = useState(!initialMarkets || initialMarkets.length === 0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>("All");
  const [cat, setCat] = useState<(typeof CATS)[number]>("All");
  const [sport, setSport] = useState("live");

  useEffect(() => {
    let dead = false;
    setLoading(true);
    void loadMarketsOrFallback(0).then(
      ({ markets: rows, fetched, total: nextTotal, source }) => {
        if (dead) return;
        setSeedFallback(source === "seed");
        if (rows.length > 0) {
          setMarkets(rows);
          setLoadedCount(fetched);
          setTotal(nextTotal);
        } else {
          setMarkets((prev) => (prev.length > 0 ? prev : rows));
          if (fetched > 0) setLoadedCount(fetched);
          if (nextTotal > 0) setTotal(nextTotal);
        }
        setLoading(false);
      },
    );
    return () => {
      dead = true;
    };
  }, []);

  async function loadMore() {
    if (loadingMore || loadedCount >= total) return;
    setLoadingMore(true);
    try {
      const { markets: rows, fetched, total: nextTotal } = await loadMarketsOrFallback(
        loadedCount,
      );
      setMarkets((prev) => {
        const seen = new Set(prev.map((m) => m.id));
        const appended = rows.filter((m) => !seen.has(m.id));
        return appended.length > 0 ? [...prev, ...appended] : prev;
      });
      setLoadedCount((prev) => prev + fetched);
      if (nextTotal > 0) setTotal(nextTotal);
    } finally {
      setLoadingMore(false);
    }
  }

  const filtered = useMemo(() => {
    let list = activeTrendingMarkets(markets);
    if (cat !== "All") list = list.filter((m) => m.category === cat);
    if (platform === "Polymarket") {
      list = list.filter((m) => m.source === "polymarket" || !m.source || m.source === "seed");
    } else if (platform === "Kalshi") {
      list = list.filter((m) => m.source === "kalshi");
    }
    // "Live" sports filter is soft: prefer live-ish rows, but never blank the board.
    if (cat === "Sports" && sport === "live") {
      const live = list.filter(isLiveish);
      if (live.length > 0) list = live;
    }
    return list;
  }, [markets, cat, platform, sport]);

  const grouped = useMemo(() => {
    const map = new Map<string, Market[]>();
    for (const m of filtered) {
      const key = m.category || "Markets";
      const arr = map.get(key) ?? [];
      arr.push(m);
      map.set(key, arr);
    }
    return [...map.entries()];
  }, [filtered]);

  return (
    <div className="mx-auto flex max-w-[1600px] gap-4 px-3 py-4 sm:px-4">
      <aside className="hidden w-[200px] shrink-0 lg:block">
        <p className="mb-2 px-2 text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
          Categories
        </p>
        <ul className="space-y-0.5">
          {SPORT_SIDEBAR.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => {
                  setCat("Sports");
                  setSport(s.id);
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[13px] transition",
                  sport === s.id && cat === "Sports"
                    ? "bg-surface-2 font-semibold text-text"
                    : "text-muted hover:bg-surface hover:text-text",
                )}
              >
                {s.id === "live" ? (
                  <span className="h-1.5 w-1.5 rounded-full bg-danger animate-pulse" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-surface-3" />
                )}
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <div className="min-w-0 flex-1">
        <h1 className="mb-3 text-[22px] font-black tracking-tight text-text">Markets</h1>
        {seedFallback ? (
          <p className="mb-4 text-center text-xs text-muted-2">
            Showing seed market catalog. Connect the API to browse live markets.
          </p>
        ) : null}
        <div className="no-scrollbar mb-3 flex gap-2 overflow-x-auto">
          {PLATFORMS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPlatform(p)}
              className={cn(
                "shrink-0 rounded-lg border px-3 py-1.5 text-xs font-bold transition",
                platform === p
                  ? "border-primary/50 bg-primary-dim text-primary"
                  : "border-border text-muted hover:text-text",
              )}
            >
              {p}
            </button>
          ))}
        </div>

        <div className="no-scrollbar mb-4 flex gap-1 overflow-x-auto border-b border-border">
          {CATS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCat(c)}
              className={cn(
                "relative shrink-0 px-3 py-2.5 text-sm font-semibold transition",
                cat === c ? "text-text" : "text-muted hover:text-text",
              )}
            >
              {c}
              {cat === c ? (
                <motion.span
                  layoutId="markets-cat"
                  className="absolute inset-x-1 bottom-0 h-0.5 rounded-full bg-danger"
                />
              ) : null}
            </button>
          ))}
          <Link
            href="/resolved"
            className="ml-auto shrink-0 px-3 py-2.5 text-sm font-semibold text-muted transition hover:text-text"
          >
            Longshots / Decided
          </Link>
        </div>

        <h2 className="mb-3 flex items-center gap-2 text-[15px] font-bold uppercase tracking-[0.08em] text-muted">
          {cat === "Sports" ? (
            <>
              <span className="h-2 w-2 rounded-full bg-danger animate-pulse" />
              Live
            </>
          ) : (
            cat
          )}
        </h2>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="skeleton h-28 w-full rounded-[12px]" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm text-muted">No markets match this filter right now.</p>
            <p className="mx-auto mt-2 max-w-sm text-xs leading-relaxed text-muted-2">
              Try another category or platform, or clear filters to browse the full live catalog.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {grouped.map(([group, rows]) => (
              <section key={group}>
                <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-muted">
                  {group}
                </h3>
                <ul className="space-y-2.5">
                  {rows.map((m, i) => {
                    const yes = m.outcomes[0];
                    const no = m.outcomes[1];
                    const yesC = Math.round((yes?.price ?? 0.5) * 100);
                    const noC = Math.round((no?.price ?? 1 - (yes?.price ?? 0.5)) * 100);
                    const teams = splitTeams(m.title);
                    const lifecycle = marketLifecycle(m);
                    const live = !seedFallback && lifecycle === "live" && isLiveish(m);
                    return (
                      <motion.li
                        key={m.id}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(i * 0.03, 0.2) }}
                        className={cn(
                          "rounded-[12px] border bg-surface p-3.5 transition hover:border-border-light",
                          live ? "border-danger/40 shadow-[0_0_0_1px_rgba(255,90,95,0.08)]" : "border-border",
                        )}
                      >
                        <div className="mb-2.5 flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-wide">
                          {live ? (
                            <span className="rounded bg-danger/15 px-1.5 py-0.5 text-danger">
                              LIVE
                            </span>
                          ) : null}
                          <span className="text-muted-2">{formatCompactUSD(m.volume)} Vol.</span>
                          {/* D03: deep-link to the desk Intelligence anchor */}
                          <Link
                            href={marketIntelHref(m.slug)}
                            className="ml-auto text-[11px] font-semibold normal-case tracking-normal text-muted transition hover:text-primary"
                          >
                            Intel ↗
                          </Link>
                          <Link
                            href={`/trade?slug=${encodeURIComponent(m.slug)}`}
                            className="text-[11px] font-semibold normal-case tracking-normal text-muted transition hover:text-primary"
                          >
                            Game View ↗
                          </Link>
                        </div>

                        {teams ? (
                          <div className="mb-3 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
                            {/* D04: min-w-0 — grid items default to min-width:auto,
                                so a long nowrap (truncate) team name forced this
                                column past the card at 390px. */}
                            <div className="min-w-0 space-y-2.5">
                              {teams.map((team, ti) => (
                                <div key={team} className="flex items-center gap-2.5">
                                  <span className="grid h-9 w-9 place-items-center rounded-full border border-border bg-surface-2 text-[10px] font-black text-primary">
                                    {initials(team)}
                                  </span>
                                  <div className="min-w-0 flex-1">
                                    <span className="block truncate text-[14px] font-semibold text-text">
                                      {team}
                                    </span>
                                    <span className="font-mono text-[10px] text-muted-2">
                                      {ti === 0 ? "Home" : "Away"} · ML
                                    </span>
                                  </div>
                                  <span
                                    className={cn(
                                      "font-mono text-[15px] font-black tabular-nums",
                                      ti === 0 ? "text-primary" : "text-danger",
                                    )}
                                  >
                                    {ti === 0 ? yesC : noC}¢
                                  </span>
                                </div>
                              ))}
                            </div>
                            <div className="hidden flex-col justify-center gap-1 border-l border-border pl-3 sm:flex">
                              <span className="text-[9px] font-bold uppercase tracking-wider text-muted-2">
                                Clock
                              </span>
                              <span className="font-mono text-[12px] font-bold text-text">Q1 12:00</span>
                              <span className="text-[10px] text-muted">Paper sim</span>
                            </div>
                            <div className="flex items-stretch gap-2 sm:flex-col">
                              <Link
                                href={marketHref(m.slug, { side: "yes" })}
                                className="min-w-[100px] flex-1 rounded-lg border border-primary/40 bg-primary-dim px-3 py-2.5 text-center font-mono text-[12px] font-bold text-primary transition hover:bg-primary hover:text-bg"
                              >
                                Paper buy {initials(teams[0])}
                              </Link>
                              <Link
                                href={marketHref(m.slug, { side: "no" })}
                                className="min-w-[100px] flex-1 rounded-lg border border-danger/40 bg-danger-dim px-3 py-2.5 text-center font-mono text-[12px] font-bold text-danger transition hover:bg-danger hover:text-bg"
                              >
                                Paper buy {initials(teams[1])}
                              </Link>
                            </div>
                          </div>
                        ) : (
                          <div className="mb-3 flex flex-wrap items-start gap-3">
                            <Link
                              href={marketHref(m.slug)}
                              className="min-w-0 flex-1 text-[14px] font-bold text-text hover:text-primary"
                            >
                              {m.title}
                            </Link>
                            <div className="flex flex-wrap gap-2">
                              <Link
                                href={marketHref(m.slug, { side: "yes" })}
                                className="rounded-lg border border-primary/40 bg-primary-dim px-3 py-2 font-mono text-[12px] font-bold text-primary"
                              >
                                {yes?.label ?? "Yes"} {yesC}¢
                              </Link>
                              <Link
                                href={marketHref(m.slug, { side: "no" })}
                                className="rounded-lg border border-danger/40 bg-danger-dim px-3 py-2 font-mono text-[12px] font-bold text-danger"
                              >
                                {no?.label ?? "No"} {noC}¢
                              </Link>
                            </div>
                          </div>
                        )}

                        <button
                          type="button"
                          onClick={() =>
                            openPanel({
                              mode: "analyze",
                              marketSlug: m.slug,
                              marketTitle: m.title,
                              seedPrompt: `Analyze live market ${m.title}.`,
                            })
                          }
                          className="w-full rounded-lg border border-primary/30 bg-primary-dim/40 py-2 text-[11px] font-bold text-primary transition hover:bg-primary hover:text-bg"
                        >
                          ✦ AI Analyze
                        </button>
                      </motion.li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
        )}

        {!loading && !seedFallback && total > 0 ? (
          <div className="mt-6 flex flex-col items-center gap-3">
            <p className="text-sm text-muted">
              Showing {loadedCount} of {total} markets
            </p>
            {loadedCount < total ? (
              <button
                type="button"
                onClick={() => void loadMore()}
                disabled={loadingMore}
                className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold text-text transition hover:border-border-light hover:bg-surface-2 disabled:cursor-wait disabled:opacity-60"
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
