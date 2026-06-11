"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useAuth } from "@/hooks/useAuth";
import { useInterval } from "@/hooks/useInterval";
import { fetchPortfolioSummary, type PortfolioSummary } from "@/lib/portfolio-api";
import { API_BASE } from "@/lib/alphaedge-api";

function formatUSD(v: number) {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function signedPct(pct: number) {
  return (pct >= 0 ? "+" : "") + pct.toFixed(2) + "%";
}

export function PortfolioBanner() {
  const { token } = useAuth();
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) {
      setSummary(null);
      return;
    }
    const data = await fetchPortfolioSummary(token, {
      apiBase: API_BASE || "http://localhost:8000",
    });
    setSummary(data);
  }, [token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useInterval(refresh, 60_000);

  if (!token || !summary) return null;

  const pnl = summary.unrealized_pnl;
  const pnlPct = summary.unrealized_pnl_pct;
  const isProfit = pnl >= 0;

  if (collapsed) {
    return (
      <div className="fixed bottom-4 right-4 z-40 sm:bottom-6 sm:right-6">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface shadow-lg transition hover:brightness-110"
          aria-label="Expand portfolio banner"
        >
          💼
        </button>
      </div>
    );
  }

  return (
    <div className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-2 sm:text-[11px]">
          Portfolio
        </span>

        <div className="flex flex-1 flex-wrap items-center gap-x-4 gap-y-1">
          {/* Bankroll */}
          <div className="flex items-baseline gap-1">
            <span className="text-[10px] text-muted-2 sm:text-xs">Bankroll</span>
            <span className="font-mono text-xs font-bold text-text sm:text-sm">
              {formatUSD(summary.bankroll)}
            </span>
          </div>

          {/* Open positions */}
          <div className="flex items-baseline gap-1">
            <span className="text-[10px] text-muted-2 sm:text-xs">Positions</span>
            <span className="font-mono text-xs font-semibold text-text">
              {summary.open_positions}
            </span>
          </div>

          {/* P&L */}
          <div className="flex items-baseline gap-1">
            <span className="text-[10px] text-muted-2 sm:text-xs">Unreal. P&L</span>
            <span
              className={cn(
                "font-mono text-xs font-bold sm:text-sm",
                isProfit ? "text-primary" : "text-danger",
              )}
            >
              {pnl >= 0 ? "+" : ""}${Math.abs(pnl).toFixed(2)}
            </span>
            <span
              className={cn(
                "font-mono text-[10px] sm:text-xs",
                isProfit ? "text-primary" : "text-danger",
              )}
            >
              ({signedPct(pnlPct)})
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/portfolio"
            className="text-[11px] font-semibold text-accent hover:underline"
          >
            View
          </Link>
          {/* Collapse to icon on mobile */}
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="text-muted-2 hover:text-text sm:hidden"
            aria-label="Collapse portfolio banner"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
