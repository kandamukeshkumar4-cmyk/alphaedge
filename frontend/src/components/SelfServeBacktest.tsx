"use client";

// X01 — self-serve per-market backtest (backend K01). A market picker (unified
// search typeahead + resolved-market quick picks from the shared fetchMarkets
// cache) that runs GET /api/v1/backtest/run?slug= and renders the per-market
// walk-forward result in the BacktestWalkForward SVG style, BESIDE the aggregate.
// Honest not-ran / thin-data / unknown-slug states — never a fabricated curve.
// Read-only compute: nothing is persisted and no order path is touched.
import { useEffect, useRef, useState } from "react";

import {
  buildBacktestRunView,
  EDGE_THRESHOLD_MAX,
  EDGE_THRESHOLD_MIN,
  fetchBacktestRunForSlug,
  STAKE_MAX,
  STAKE_MIN,
  type BacktestRunParams,
  type BacktestRunView,
  type SeriesPoint,
} from "@/lib/backtest-run-api";
import { cn } from "@/lib/cn";
import { fetchMarkets, type Market } from "@/lib/markets-api";
import { searchUnified, type UnifiedSearchResult } from "@/lib/search-api";

function WalkForwardLine({
  series,
  label,
  stroke,
  fill,
  formatValue,
}: {
  series: SeriesPoint[];
  label: string;
  stroke: string;
  fill: string;
  formatValue: (v: number) => string;
}) {
  const w = 320;
  const h = 140;
  const pad = 22;
  const values = series.map((s) => s.value);
  const maxV = Math.max(0.02, ...values);
  const minV = Math.min(0, ...values);
  const span = maxV - minV || 1;
  const px = (i: number) =>
    pad + (series.length <= 1 ? 0 : (i / (series.length - 1)) * (w - pad * 2));
  const py = (v: number) => pad + (1 - (v - minV) / span) * (h - pad * 2);
  const d = series.map((s, i) => `${i === 0 ? "M" : "L"}${px(i)},${py(s.value)}`).join(" ");
  const last = series[series.length - 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-auto w-full" role="img" aria-label={label}>
      <title>{label}</title>
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} className="stroke-border" strokeWidth={1} />
      <path d={d} className={cn("fill-none", stroke)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {series.map((s, i) => (
        <circle key={s.seq} cx={px(i)} cy={py(s.value)} r={2.5} className={fill}>
          <title>{`resolution ${s.seq}: ${formatValue(s.value)}`}</title>
        </circle>
      ))}
      <text x={w - pad} y={py(last.value) - 6} textAnchor="end" className="fill-muted-2 text-[9px] font-mono">
        {formatValue(last.value)}
      </text>
    </svg>
  );
}

function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/60 px-3.5 py-2">
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">{label}</p>
      <p className={cn("font-mono text-xl font-black", tone ?? "text-text")}>{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-muted-2">{hint}</p> : null}
    </div>
  );
}

function RunResult({ view }: { view: BacktestRunView }) {
  if (!view.reachable) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-6 text-center">
        <p className="text-sm font-semibold text-text">Backtest API unreachable</p>
        <p className="mx-auto mt-1.5 max-w-md text-xs text-muted">
          The live API did not answer — start the backend or set NEXT_PUBLIC_API_URL to run a
          self-serve backtest.
        </p>
      </div>
    );
  }

  if (!view.ran) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface p-6 text-center">
        <p className="text-sm font-semibold text-text">No backtest for this market</p>
        <p className="mx-auto mt-1.5 max-w-md text-xs text-muted">{view.notRanMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {view.caveat ? (
        <div className="flex items-start gap-2 rounded-xl border border-gold/40 bg-gold/10 px-4 py-3">
          <span className="mt-0.5 rounded-pill bg-gold/20 px-2 py-0.5 font-mono text-[10px] font-black uppercase text-gold">
            Provisional
          </span>
          <p className="text-sm font-semibold text-gold">{view.caveat}</p>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile
          label="Resolved"
          value={`n=${view.nLabel}`}
          hint={view.lastUpdatedLabel ? `updated ${view.lastUpdatedLabel}` : undefined}
        />
        <Tile label="Model Brier" value={view.brierLabel} hint={view.brierVerdict ?? undefined} />
        <Tile label="Market Brier" value={view.marketBrierLabel} hint="implied-price baseline" />
        <Tile
          label="Flat-stake ROI"
          value={view.roiLabel}
          hint={`${view.betsLabel} bets · ${view.pnlLabel} paper P&L`}
          tone={view.roiTone === "up" ? "text-up" : view.roiTone === "down" ? "text-danger" : "text-text"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <h3 className="text-sm font-black tracking-tight text-text">Walk-forward Brier</h3>
          <p className="mt-0.5 text-[11px] text-muted-2">Cumulative Brier per real resolution — lower is better.</p>
          {view.hasBrierSeries ? (
            <div className="mt-3">
              <WalkForwardLine
                series={view.brierSeries}
                label={`Walk-forward cumulative Brier for ${view.slug} (lower is better)`}
                stroke="stroke-accent"
                fill="fill-accent"
                formatValue={(v) => v.toFixed(3)}
              />
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted">Fewer than 2 resolutions — no line to draw yet.</p>
          )}
        </div>
        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <h3 className="text-sm font-black tracking-tight text-text">Walk-forward ROI</h3>
          <p className="mt-0.5 text-[11px] text-muted-2">Cumulative flat-stake (1-contract) paper ROI — starts at the first bet.</p>
          {view.hasRoiSeries ? (
            <div className="mt-3">
              <WalkForwardLine
                series={view.roiSeries}
                label={`Walk-forward cumulative flat-stake paper ROI for ${view.slug}`}
                stroke="stroke-primary"
                fill="fill-primary"
                formatValue={(v) => `${(v * 100).toFixed(0)}%`}
              />
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted">Fewer than 2 bets so far — the ROI line starts at the first bet.</p>
          )}
        </div>
      </div>

      <p className="text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
    </div>
  );
}

/** Parse a controlled numeric input into a finite number or null (= default). */
function parseParam(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
}

export function SelfServeBacktest() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<UnifiedSearchResult[]>([]);
  const [quickPicks, setQuickPicks] = useState<Market[]>([]);
  const [openList, setOpenList] = useState(false);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [activeTitle, setActiveTitle] = useState<string>("");
  const [view, setView] = useState<BacktestRunView | null>(null);
  const [running, setRunning] = useState(false);
  // Y01 — L01 strategy knobs. Empty string = the K01 default (param omitted).
  const [edgeInput, setEdgeInput] = useState("");
  const [stakeInput, setStakeInput] = useState("");
  const runCtrl = useRef<AbortController | null>(null);

  // Resolved-market quick picks from the shared markets cache (no raw poll loop).
  useEffect(() => {
    let dead = false;
    void fetchMarkets("resolved")
      .then((markets) => {
        if (!dead) setQuickPicks(markets.slice(0, 6));
      })
      .catch(() => {
        if (!dead) setQuickPicks([]);
      });
    return () => {
      dead = true;
    };
  }, []);

  // Typeahead against the unified search endpoint (debounced).
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      void searchUnified(q, 8, ctrl.signal)
        .then((rows) => setSuggestions(rows))
        .catch(() => setSuggestions([]));
    }, 200);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [query]);

  function select(slug: string, title: string) {
    setActiveSlug(slug);
    setActiveTitle(title);
    setOpenList(false);
    setQuery(title);
  }

  // Fetch whenever the picked market OR the strategy params change. Debounced so
  // typing an edge/stake value does not spam the endpoint, and aborted on change
  // — reuses the same read-only run, never a raw poll loop.
  const edgeThreshold = parseParam(edgeInput);
  const stake = parseParam(stakeInput);
  useEffect(() => {
    if (!activeSlug) return;
    setRunning(true);
    setView(null);
    const ctrl = new AbortController();
    runCtrl.current?.abort();
    runCtrl.current = ctrl;
    const params: BacktestRunParams = { edgeThreshold, stake };
    const t = setTimeout(() => {
      void fetchBacktestRunForSlug(activeSlug, params, ctrl.signal)
        .then((raw) => {
          if (ctrl.signal.aborted) return;
          setView(buildBacktestRunView(raw));
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setRunning(false);
        });
    }, 250);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [activeSlug, edgeThreshold, stake]);

  useEffect(() => () => runCtrl.current?.abort(), []);

  return (
    <div className="space-y-4">
      <div className="relative">
        <label htmlFor="backtest-market-search" className="sr-only">
          Search a market to backtest
        </label>
        <input
          id="backtest-market-search"
          type="search"
          role="combobox"
          aria-expanded={openList}
          aria-controls="backtest-market-suggestions"
          aria-label="Search a market to backtest"
          autoComplete="off"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpenList(true);
          }}
          onFocus={() => setOpenList(true)}
          placeholder="Search a resolved market to backtest…"
          className="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-text outline-none transition focus:border-accent"
        />

        {openList && (suggestions.length > 0 || query.trim().length >= 2) ? (
          <ul
            id="backtest-market-suggestions"
            role="listbox"
            aria-label="Market search results"
            className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-border bg-surface shadow-lg"
          >
            {suggestions.length === 0 ? (
              <li className="px-4 py-3 text-xs text-muted-2">No markets match “{query.trim()}”.</li>
            ) : (
              suggestions.map((s) => (
                <li key={s.slug} role="option" aria-selected={s.slug === activeSlug}>
                  <button
                    type="button"
                    onClick={() => select(s.slug, s.title)}
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-left transition hover:bg-surface-2"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm text-text">{s.title}</span>
                    <span className="shrink-0 rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-2">
                      {s.platform}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
        ) : null}
      </div>

      {quickPicks.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wide text-muted-2">Recently resolved</span>
          {quickPicks.map((m) => (
            <button
              key={m.slug}
              type="button"
              onClick={() => select(m.slug, m.title)}
              className={cn(
                "max-w-[220px] truncate rounded-pill border px-2.5 py-1 text-[11px] font-semibold transition",
                m.slug === activeSlug
                  ? "border-accent/50 bg-accent-dim text-accent"
                  : "border-border text-muted hover:border-border-light hover:text-text",
              )}
              title={m.title}
            >
              {m.title}
            </button>
          ))}
        </div>
      ) : null}

      {activeSlug ? (
        <div className="rounded-2xl border border-border bg-surface/60 p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-black text-text">{activeTitle || activeSlug}</h3>
            <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] text-muted-2">{activeSlug}</span>
          </div>

          {/* Y01 — L01 strategy knobs. Re-runs the read-only backtest on change. */}
          <div className="mb-4 rounded-xl border border-border bg-surface-2/40 p-3 sm:p-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">Strategy params</p>
            <div className="mt-2 flex flex-wrap gap-3">
              <div className="min-w-0 flex-1 basis-40">
                <label htmlFor="backtest-edge-threshold" className="block text-[11px] font-semibold text-muted">
                  Edge threshold ({EDGE_THRESHOLD_MIN}–{EDGE_THRESHOLD_MAX})
                </label>
                <input
                  id="backtest-edge-threshold"
                  type="number"
                  inputMode="decimal"
                  min={EDGE_THRESHOLD_MIN}
                  max={EDGE_THRESHOLD_MAX}
                  step={0.01}
                  value={edgeInput}
                  onChange={(e) => setEdgeInput(e.target.value)}
                  aria-label="Minimum model-vs-market edge to place a paper bet"
                  placeholder="default"
                  className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-1.5 font-mono text-sm text-text outline-none transition focus:border-accent"
                />
              </div>
              <div className="min-w-0 flex-1 basis-40">
                <label htmlFor="backtest-stake" className="block text-[11px] font-semibold text-muted">
                  Flat stake ({STAKE_MIN}–{STAKE_MAX})
                </label>
                <input
                  id="backtest-stake"
                  type="number"
                  inputMode="decimal"
                  min={STAKE_MIN}
                  max={STAKE_MAX}
                  step={0.5}
                  value={stakeInput}
                  onChange={(e) => setStakeInput(e.target.value)}
                  aria-label="Flat paper stake size per bet"
                  placeholder="1.0"
                  className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-1.5 font-mono text-sm text-text outline-none transition focus:border-accent"
                />
              </div>
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-muted-2">
              Brier is scored over <strong>all</strong> resolved forecasts — edge threshold and
              stake never change it. Only <strong>bet count</strong>, paper P&amp;L and ROI respond
              (ROI is stake-invariant). Empty = the desk default; out-of-range values are clamped.
            </p>
          </div>

          {running || view === null ? (
            <div className="grid gap-3 sm:grid-cols-2" aria-hidden>
              {[0, 1].map((i) => (
                <div key={i} className="skeleton h-40 rounded-2xl" />
              ))}
            </div>
          ) : (
            <RunResult view={view} />
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-surface/50 px-6 py-10 text-center">
          <p className="text-sm font-semibold text-text">Pick a market to backtest</p>
          <p className="mx-auto mt-1.5 max-w-sm text-xs text-muted">
            Search above or tap a recently-resolved market. We replay this desk&apos;s real
            forecast history for that one market — walk-forward Brier and flat-stake paper ROI.
            Nothing is fabricated: markets without enough resolved history show an honest empty state.
          </p>
        </div>
      )}
    </div>
  );
}
