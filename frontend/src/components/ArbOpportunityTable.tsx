"use client";

/**
 * ArbOpportunityTable — U11 Cross-platform arb hardening
 *
 * Displays detected PM↔Kalshi arb signal opportunities.
 * Signal only — never auto-traded.
 */

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { API_BASE } from "@/lib/alphaedge-api";

// ---------------------------------------------------------------------------
// Types (matches backend ArbOpportunityOut schema)
// ---------------------------------------------------------------------------

export interface ArbOpportunityRow {
  id: string;
  pm_market_id: string;
  kalshi_market_id: string;
  pm_title: string;
  kalshi_title: string;
  match_confidence: number;
  match_reasons: string[];
  combined_price: string;
  theoretical_edge: string;
  gross_spread: string;
  is_arbitrage: boolean;
  warning: string;
  detected_at: string;
  expires_at: string;
  stale: boolean;
  signal_only: boolean;
  seconds_until_stale: number;
}

interface ArbPageResponse {
  opportunities: ArbOpportunityRow[];
  total: number;
  fresh_count: number;
  stale_count: number;
  signal_only: boolean;
  note: string;
}

// ---------------------------------------------------------------------------
// Staleness countdown hook
// ---------------------------------------------------------------------------

function useCountdown(expiresAt: string, initialSeconds: number, stale: boolean) {
  const [seconds, setSeconds] = useState(initialSeconds);

  useEffect(() => {
    if (stale) return;
    const timer = setInterval(() => {
      const now = Date.now();
      const exp = new Date(expiresAt).getTime();
      const remaining = Math.max(0, Math.floor((exp - now) / 1000));
      setSeconds(remaining);
      if (remaining <= 0) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [expiresAt, stale]);

  return seconds;
}

// ---------------------------------------------------------------------------
// Single row with live countdown
// ---------------------------------------------------------------------------

function ArbRow({ opp }: { opp: ArbOpportunityRow }) {
  const seconds = useCountdown(opp.expires_at, opp.seconds_until_stale, opp.stale);
  const isStale = opp.stale || seconds <= 0;

  const edgePct = parseFloat(opp.theoretical_edge);
  const edgeLabel = isNaN(edgePct)
    ? opp.theoretical_edge
    : `${(edgePct * 100).toFixed(2)}%`;
  const confidencePct = `${(opp.match_confidence * 100).toFixed(0)}%`;

  const stalenessLabel = isStale
    ? "Stale"
    : seconds < 60
      ? `${seconds}s`
      : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;

  return (
    <tr
      className={cn(
        "border-t border-border/70 transition-opacity",
        isStale ? "opacity-40" : "opacity-100",
      )}
    >
      {/* PM Market */}
      <td className="px-4 py-3">
        <p className={cn("text-sm font-semibold", isStale ? "text-muted" : "text-text")}>
          {opp.pm_title}
        </p>
        <p className="mt-0.5 text-xs text-muted">{opp.pm_market_id}</p>
      </td>
      {/* Kalshi Market */}
      <td className="px-4 py-3">
        <p className={cn("text-sm font-semibold", isStale ? "text-muted" : "text-text")}>
          {opp.kalshi_title}
        </p>
        <p className="mt-0.5 text-xs text-muted">{opp.kalshi_market_id}</p>
      </td>
      {/* Match confidence */}
      <td className="px-4 py-3">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold",
            opp.match_confidence >= 0.75
              ? "bg-primary/15 text-primary"
              : opp.match_confidence >= 0.50
                ? "bg-gold/15 text-gold"
                : "bg-surface-2 text-muted",
          )}
          title={opp.match_reasons.join(", ")}
        >
          {confidencePct}
        </span>
      </td>
      {/* Combined price */}
      <td className="px-4 py-3 font-mono text-sm text-text">
        {opp.combined_price}
      </td>
      {/* Theoretical edge */}
      <td className="px-4 py-3 font-mono text-sm">
        <span
          className={cn(
            "font-bold",
            opp.is_arbitrage && !isStale ? "text-up" : "text-muted",
          )}
        >
          {edgeLabel}
        </span>
      </td>
      {/* Staleness countdown */}
      <td className="px-4 py-3 text-sm">
        <span
          className={cn(
            "font-mono font-bold",
            isStale ? "text-muted" : seconds < 30 ? "text-danger" : "text-text",
          )}
        >
          {stalenessLabel}
        </span>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ArbOpportunityTable() {
  const [data, setData] = useState<ArbPageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function loadOpportunities() {
    if (!API_BASE) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/arb/opportunities?include_stale=true`);
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const json = (await res.json()) as ArbPageResponse;
      setData(json);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load arb opportunities");
    }
  }

  useEffect(() => {
    setLoading(true);
    void loadOpportunities().finally(() => setLoading(false));

    // Refresh every 30 seconds to pick up new detections.
    pollRef.current = setInterval(() => void loadOpportunities(), 30_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const opportunities = data?.opportunities ?? [];
  const hasData = opportunities.length > 0;

  return (
    <section>
      {/* Signal-only disclaimer — always visible */}
      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl bg-gold/10 px-4 py-2.5">
        <span className="text-xs font-bold uppercase tracking-wide text-gold">
          Signal only — never auto-traded
        </span>
        <span className="text-xs text-muted">
          AlphaEdge detects PM↔Kalshi price discrepancies as informational signals.
          No order is ever placed automatically.
        </span>
      </div>

      {/* Stats row */}
      {data && (
        <div className="mb-4 flex flex-wrap gap-4 text-sm">
          <div>
            <span className="font-bold text-text">{data.fresh_count}</span>{" "}
            <span className="text-muted">fresh</span>
          </div>
          <div>
            <span className="font-bold text-muted">{data.stale_count}</span>{" "}
            <span className="text-muted">stale</span>
          </div>
          <div>
            <span className="font-bold text-text">{data.total}</span>{" "}
            <span className="text-muted">total</span>
          </div>
        </div>
      )}

      {/* Loading / error / empty states */}
      {!API_BASE && (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          Set <code className="rounded bg-surface-2 px-1">NEXT_PUBLIC_API_URL</code> to load
          live arb signals.
        </div>
      )}

      {API_BASE && loading && !hasData && (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          Loading arb signals…
        </div>
      )}

      {API_BASE && error && (
        <div className="rounded-2xl border border-dashed border-border bg-danger/10 px-4 py-6 text-center text-sm text-danger">
          {error}
        </div>
      )}

      {API_BASE && !loading && !error && !hasData && (
        <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          <p className="font-semibold text-text">No arbitrage opportunities detected</p>
          <p className="mt-1">
            When PM and Kalshi price the same event differently, a signal will appear
            here. Opportunities refresh every 30 seconds.
          </p>
        </div>
      )}

      {hasData && (
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-2 text-xs font-bold uppercase tracking-[0.06em] text-muted">
              <tr>
                <th className="px-4 py-3">Polymarket</th>
                <th className="px-4 py-3">Kalshi</th>
                <th className="px-4 py-3">Match confidence</th>
                <th className="px-4 py-3">Combined price</th>
                <th className="px-4 py-3">Theoretical edge</th>
                <th className="px-4 py-3">Expires in</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((opp) => (
                <ArbRow key={opp.id} opp={opp} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Bottom note */}
      <p className="mt-3 text-xs text-muted">
        Match confidence is a weighted score (event_id + entity + close time + title
        tokens). Opportunities with a grey background have exceeded their{" "}
        {Math.floor((data?.opportunities?.[0]?.seconds_until_stale ?? 300) / 60) || 5}-minute
        TTL and are stale. PAPER TRADING ONLY.
      </p>
    </section>
  );
}
