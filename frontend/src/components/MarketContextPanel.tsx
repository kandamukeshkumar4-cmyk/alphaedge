"use client";

/**
 * Loop V60 (U4) — market context panel on the market detail page.
 * Reads GET /api/v1/markets/{slug}/context once on mount and renders the
 * master context snapshot: whale-pressure gauge, venue gap, news tone, price
 * trend, and volume pace. Every number is descriptive telemetry ("what the
 * feed reports") — the panel never suggests a position, an edge, or any
 * action. If the context endpoint 404s the panel says so honestly; no
 * synthetic or cached values are ever shown. Read-only; there is no order
 * path here.
 */

import { useCallback, useEffect, useState } from "react";

import { relativeTime } from "@/lib/alerts-api";
import { cn } from "@/lib/cn";
import {
  fetchMarketContext,
  formatSignedPct,
  formatVenueGap,
  formatVolumePct,
  newsSignalTone,
  whalePressurePct,
  whalePressureTier,
  type MarketContextResponse,
  type NewsSignalTone,
  type PodsApiResult,
  type WhalePressureTier,
} from "@/lib/pods-api";

type PanelState =
  | { phase: "loading" }
  | { phase: "ready"; result: PodsApiResult<MarketContextResponse> };

export function MarketContextPanel({ slug }: { slug: string }) {
  const [state, setState] = useState<PanelState>({ phase: "loading" });

  const load = useCallback(async () => {
    const result = await fetchMarketContext(slug);
    setState({ phase: "ready", result });
  }, [slug]);

  useEffect(() => {
    setState({ phase: "loading" });
    void load();
  }, [load]);

  const response = state.phase === "ready" ? state.result : null;
  const statusDot =
    state.phase === "loading"
      ? "bg-muted-2"
      : response?.ok
        ? "bg-accent animate-pulse-soft"
        : "bg-danger";

  return (
    <section
      aria-label="Market context"
      className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-mono text-[12px] font-black uppercase tracking-[0.14em] text-text">
            Market context
          </h2>
          <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2">
            GET /api/v1/markets/{"{slug}"}/context
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted">
          <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", statusDot)} />
          snapshot
        </span>
      </header>

      <div className="p-4">
        {state.phase === "loading" ? (
          <div className="space-y-2" aria-hidden>
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-10 w-full" />
            ))}
          </div>
        ) : response && !response.ok ? (
          <MarketContextUnavailable reason={response.reason} />
        ) : response?.ok ? (
          <MarketContextReady context={response.data} />
        ) : null}
      </div>
    </section>
  );
}

/** Gauge fill color by intensity tier — describes concentration, not direction. */
const GAUGE_FILL: Record<WhalePressureTier, string> = {
  quiet: "bg-muted-2",
  building: "bg-accent",
  heavy: "bg-amber-400",
};

const NEWS_CHIP: Record<NewsSignalTone, string> = {
  positive: "bg-primary-dim text-primary",
  negative: "bg-danger-dim text-danger",
  neutral: "bg-surface-3 text-muted",
};

/**
 * The populated snapshot. Exported so tests can render this branch directly
 * (effects/fetch never run under renderToStaticMarkup).
 */
export function MarketContextReady({ context }: { context: MarketContextResponse }) {
  const whalePct = whalePressurePct(context.whale_pressure);
  const tier = whalePressureTier(context.whale_pressure);
  const tone = newsSignalTone(context.news_signal);
  const trend = clampTrend(context.price_trend);
  const captured = relativeTime(context.captured_at);

  return (
    <div className="space-y-4">
      {/* Whale pressure gauge */}
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
            Whale pressure
          </p>
          <p className="font-mono text-xs font-bold tabular-nums text-text">
            {whalePct}
            <span className="ml-1 text-[10px] font-bold uppercase tracking-[0.1em] text-muted">
              {tier}
            </span>
          </p>
        </div>
        <div
          role="meter"
          aria-label="Whale pressure"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={whalePct}
          className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-3"
        >
          <div
            className={cn("h-full rounded-full transition-[width]", GAUGE_FILL[tier])}
            style={{ width: `${whalePct}%` }}
          />
        </div>
        <p className="mt-1 text-[11px] text-muted">
          Share of recent flow from the largest tracked wallets.
        </p>
      </div>

      {/* Venue gap + news tone */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-border bg-surface-2 px-3 py-2.5">
          <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
            Venue gap
          </p>
          <p className="mt-0.5 font-mono text-lg font-black tabular-nums text-text">
            {formatVenueGap(context.venue_gap)}
          </p>
          <p className="mt-0.5 text-[11px] text-muted">Price difference vs the reference venue.</p>
        </div>
        <div className="rounded-xl border border-border bg-surface-2 px-3 py-2.5">
          <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
            News tone
          </p>
          <p className="mt-1">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-mono text-[10px] font-black uppercase tracking-[0.1em]",
                NEWS_CHIP[tone],
              )}
            >
              {tone}
            </span>
          </p>
          <p className="mt-1 text-[11px] text-muted">Tone of recent headlines about this market.</p>
        </div>
      </div>

      {/* Trend + volume pace */}
      <div className="grid grid-cols-2 gap-3 border-t border-border pt-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
            Price trend
          </p>
          <p
            className={cn(
              "mt-0.5 font-mono text-sm font-bold tabular-nums",
              trend > 0 ? "text-primary" : trend < 0 ? "text-danger" : "text-muted",
            )}
          >
            {formatSignedPct(context.price_trend)}
          </p>
          <p className="text-[11px] text-muted">Recent movement.</p>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">Volume</p>
          <p className="mt-0.5 font-mono text-sm font-bold tabular-nums text-text">
            {formatVolumePct(context.volume_pct)}
          </p>
          <p className="text-[11px] text-muted">Of this market&apos;s typical pace.</p>
        </div>
      </div>

      <p className="border-t border-border pt-2.5 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-2">
        {captured ? `captured ${captured}` : "capture time unknown"} · descriptive context only —
        not trading advice
      </p>
    </div>
  );
}

/** Sign of the trend for token coloring; non-finite input is neutral. */
function clampTrend(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value === 0) return 0;
  return value > 0 ? 1 : -1;
}

/**
 * Honest absent states. Exported so tests can render both reasons directly.
 */
export function MarketContextUnavailable({
  reason,
}: {
  reason: "not-deployed" | "unavailable";
}) {
  const notDeployed = reason === "not-deployed";
  return (
    <div className="py-3 text-center">
      <p className="font-mono text-[11px] font-bold uppercase tracking-[0.12em] text-muted-2">
        {notDeployed ? "Market context not yet deployed" : "Market context unavailable"}
      </p>
      <p className="mx-auto mt-1.5 max-w-md text-[11px] text-muted">
        {notDeployed
          ? "The context endpoint returned 404 — the backend is still shipping. This panel renders live context as soon as it exists; nothing is mocked."
          : "The context endpoint could not be reached. No cached or synthetic values are shown."}
      </p>
    </div>
  );
}
