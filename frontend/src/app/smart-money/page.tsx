"use client";

// F02: per-market smart-money desk from GET /api/v1/smart-money (G07).
// Read-only analysis: top holders, whale concentration, recent large flows,
// trade-intensity, depth skew. Market picker reuses the shared markets cache +
// unified search. "Paper-trade this market" CTA hands off to the trade panel.
import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { searchUnified, type UnifiedSearchResult } from "@/lib/search-api";
import {
  buildSmartMoneyView,
  fetchSmartMoney,
  type SmartMoneyView,
} from "@/lib/smart-money-api";
import { cn } from "@/lib/cn";
import { PageHeader, PageShell, Panel, StatRow, StatTile } from "@/components/ui/kit";

type Pick = { slug: string; title: string };

function MarketPicker({
  selected,
  onPick,
}: {
  selected: string | null;
  onPick: (pick: Pick) => void;
}) {
  const [suggested, setSuggested] = useState<Pick[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UnifiedSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    let dead = false;
    void fetchMarkets({ sort: "volume" }).then((markets) => {
      if (dead) return;
      setSuggested(markets.slice(0, 6).map((m) => ({ slug: m.slug, title: m.title })));
    });
    return () => {
      dead = true;
    };
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults(null);
      return;
    }
    setSearching(true);
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      void searchUnified(q, 6, ctrl.signal)
        .then((r) => setResults(r))
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 250);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [query]);

  return (
    <Panel title="Pick a market" className="mb-6">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search markets by name…"
        className="h-10 w-full rounded-xl border border-border bg-surface-2 px-3 text-sm text-text placeholder:text-muted-2 focus:border-primary/50 focus:outline-none"
        aria-label="Search markets"
      />
      {query.trim() ? (
        <div className="mt-3 space-y-1">
          {searching && results === null ? (
            <p className="text-xs text-muted-2">Searching…</p>
          ) : results && results.length > 0 ? (
            results.map((r) => (
              <button
                key={r.slug}
                type="button"
                onClick={() => {
                  onPick({ slug: r.slug, title: r.title });
                  setQuery("");
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition",
                  selected === r.slug
                    ? "border-primary/50 bg-primary/10 text-text"
                    : "border-border bg-surface hover:border-border-light hover:text-text",
                )}
              >
                <span className="truncate font-semibold text-text">{r.title}</span>
                <span className="shrink-0 font-mono text-[10px] uppercase text-muted-2">
                  {r.platform}
                </span>
              </button>
            ))
          ) : (
            <p className="text-xs text-muted">No markets match “{query.trim()}”.</p>
          )}
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {suggested.length === 0 ? (
            <p className="text-xs text-muted-2">Loading liquid markets…</p>
          ) : (
            suggested.map((m) => (
              <button
                key={m.slug}
                type="button"
                onClick={() => onPick(m)}
                className={cn(
                  "max-w-full truncate rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                  selected === m.slug
                    ? "border-primary/50 bg-primary/12 text-primary"
                    : "border-border bg-surface text-muted hover:border-border-light hover:text-text",
                )}
                title={m.title}
              >
                {m.title}
              </button>
            ))
          )}
        </div>
      )}
    </Panel>
  );
}

function IntensityBar({ ratio }: { ratio: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
      <div
        className="h-full rounded-full bg-gradient-to-r from-primary/60 to-accent"
        style={{ width: `${Math.max(4, ratio * 100)}%` }}
      />
    </div>
  );
}

function SmartMoneyDesk({
  view,
  loading,
  title,
  slug,
}: {
  view: SmartMoneyView;
  loading: boolean;
  title: string;
  slug: string;
}) {
  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl border border-border bg-surface" />
        ))}
      </div>
    );
  }

  if (!view.found) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center">
        <p className="text-base font-semibold text-text">No smart-money data for this market</p>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
          The market wasn’t found in the local venue store, or it has no whale/flow observations in
          this window yet. Try another market or widen the window.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-black text-text">{title}</h2>
          <p className="font-mono text-[11px] text-muted-2">{slug} · window {view.hoursLabel}</p>
        </div>
        <Link
          href={`/trade?slug=${encodeURIComponent(slug)}`}
          className="inline-flex h-9 shrink-0 items-center rounded-xl bg-primary px-4 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
        >
          Paper-trade this market
        </Link>
      </div>

      <StatRow cols={4}>
        <StatTile
          label="Whale concentration"
          value={view.concentrationLabel}
          hint={`${view.walletCountLabel} wallets · top holders' share`}
          accent
        />
        <StatTile label="Tracked size" value={view.totalSizeLabel} hint="shares held by top holders" />
        <StatTile
          label="Depth skew"
          value={view.depthSkewLabel}
          deltaTone={view.depthSkewTone}
          hint="+ = bid-heavy book"
        />
        <StatTile label="Fills / hour" value={view.fillsPerHourLabel} hint={`${view.fillCountLabel} fills · ${view.notionalLabel}`} />
      </StatRow>

      <Panel title="Trade intensity">
        <IntensityBar ratio={view.intensityRatio} />
        <p className="mt-2 text-xs text-muted">
          {view.fillsPerHourLabel} fills/hour over the last {view.hoursLabel} ({view.fillCountLabel}{" "}
          fills, {view.notionalLabel} notional).
        </p>
      </Panel>

      <Panel title="Recent large flows">
        {view.hasFlows ? (
          <ul className="divide-y divide-border/60">
            {view.flows.map((f, i) => (
              <li key={`${f.wallet}-${i}`} className="flex items-center justify-between gap-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "rounded-pill px-2 py-0.5 font-mono text-[10px] font-black uppercase",
                      f.isBuy ? "bg-primary/15 text-primary" : "bg-danger/15 text-danger",
                    )}
                  >
                    {f.direction}
                  </span>
                  <span className="font-mono text-xs text-muted">{f.wallet}</span>
                </div>
                <div className="flex items-center gap-3 text-right">
                  <span className="font-mono text-[11px] text-muted-2">
                    {f.action} · {f.outcome}
                  </span>
                  <span className="w-16 font-mono text-sm font-bold text-text">{f.sizeLabel}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-6 text-center text-sm text-muted">
            No large whale flows (≥100 shares) in this window.
          </p>
        )}
      </Panel>

      {view.errors.length > 0 ? (
        <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted-2">
          Some sections had no data: {view.errors.join("; ")}.
        </p>
      ) : null}
    </div>
  );
}

function SmartMoneyInner() {
  const searchParams = useSearchParams();
  const [pick, setPick] = useState<Pick | null>(null);
  const [raw, setRaw] = useState<Parameters<typeof buildSmartMoneyView>[0]>(null);
  const [loading, setLoading] = useState(false);
  const [hours, setHours] = useState(24);

  const slug = pick?.slug ?? searchParams.get("slug") ?? null;
  const title = pick?.title ?? slug ?? "";

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    const ctrl = new AbortController();
    void fetchSmartMoney(slug, { hours, topN: 5, signal: ctrl.signal }).then((data) => {
      setRaw(data);
      setLoading(false);
    });
    return () => ctrl.abort();
  }, [slug, hours]);

  const view = useMemo(() => buildSmartMoneyView(raw), [raw]);

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Smart money"
        title="Smart-money desk"
        subtitle="Whale concentration, large flows, and trade intensity per market — read-only signal. No orders are ever placed from this page."
        actions={
          <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-surface p-1">
            {[6, 24, 72].map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => setHours(h)}
                className={cn(
                  "rounded-lg px-2.5 py-1 text-xs font-bold transition",
                  hours === h ? "bg-primary text-bg" : "text-muted hover:text-text",
                )}
              >
                {h}h
              </button>
            ))}
          </div>
        }
      />

      <MarketPicker selected={slug} onPick={setPick} />

      {slug ? (
        <SmartMoneyDesk view={view} loading={loading} title={title} slug={slug} />
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-surface p-8 text-center">
          <p className="text-base font-semibold text-text">Pick a market to see its smart money</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
            Choose a liquid market above or search by name. Everything here is an observation only —
            paper trading, simulated funds, no execution.
          </p>
        </div>
      )}

      <footer className="mt-8 rounded-xl border border-border bg-surface-2 px-4 py-3 text-xs font-semibold text-muted">
        {view.disclaimer}
      </footer>
    </PageShell>
  );
}

export default function SmartMoneyPage() {
  return (
    <Suspense fallback={<div className="skeleton m-4 h-[60vh] rounded-xl" />}>
      <SmartMoneyInner />
    </Suspense>
  );
}
