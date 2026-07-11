"use client";

import { useEffect, useState } from "react";
import { fetchPortfolioRisk, type PortfolioRisk } from "@/lib/portfolio-api";
import { cn } from "@/lib/cn";
import { formatUSD } from "@/lib/mock-data";

function Stat({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: "up" | "down";
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-3" title={hint}>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-2">{label}</p>
      <p
        className={cn(
          "mt-1 font-mono text-lg font-semibold tabular-nums",
          tone === "up" && "text-primary",
          tone === "down" && "text-danger",
          !tone && "text-text",
        )}
      >
        {value}
      </p>
    </div>
  );
}

// Risk metrics over the paper book (E12): win rate, drawdown, per-trade
// Sharpe, and open exposure by category. Descriptive only — never advice.
export function PortfolioRiskPanel({ token }: { token: string }) {
  const [risk, setRisk] = useState<PortfolioRisk | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    fetchPortfolioRisk(token)
      .then((r) => {
        if (!dead) setRisk(r);
      })
      .finally(() => {
        if (!dead) setLoaded(true);
      });
    return () => {
      dead = true;
    };
  }, [token]);

  if (!loaded || risk === null) return null;

  const exposures = Object.entries(risk.exposure_pct_by_category)
    .map(([cat, pct]) => [cat, Number.isFinite(Number(pct)) ? Number(pct) : 0] as const)
    .sort((a, b) => b[1] - a[1]);

  return (
    <section className="mb-6 rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Risk metrics</h2>
      {risk.n_closed === 0 && exposures.length === 0 ? (
        <p className="mt-2 text-xs text-muted">
          Metrics appear after your first settled trade — win rate, drawdown and
          per-trade consistency are computed from your realized paper results.
        </p>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
            <Stat
              label="Realized P&L"
              value={formatUSD(risk.total_realized_pnl)}
              tone={risk.total_realized_pnl >= 0 ? "up" : "down"}
            />
            <Stat
              label="Win rate"
              value={risk.win_rate != null ? `${Math.round(risk.win_rate * 100)}%` : "—"}
              hint={`${risk.n_closed} settled trade${risk.n_closed === 1 ? "" : "s"}`}
            />
            <Stat
              label="Max drawdown"
              value={formatUSD(risk.max_drawdown)}
              tone={risk.max_drawdown > 0 ? "down" : undefined}
              hint="Largest peak-to-trough fall of cumulative realized P&L"
            />
            <Stat
              label="Sharpe (per trade)"
              value={risk.sharpe != null ? risk.sharpe.toFixed(2) : "—"}
              hint="Mean / stdev of per-trade returns. Not annualized."
            />
          </div>

          {exposures.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-2">
                Open exposure by category
              </p>
              <div className="mt-2 space-y-1.5">
                {exposures.map(([cat, pct]) => (
                  <div key={cat} className="flex items-center gap-2">
                    <span className="w-24 truncate text-xs text-muted">{cat}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
                      <div
                        className="h-full rounded-full bg-accent"
                        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                      />
                    </div>
                    <span className="w-20 text-right font-mono text-[11px] tabular-nums text-text">
                      {pct.toFixed(1)}% ·{" "}
                      {formatUSD(risk.exposure_by_category[cat] ?? 0)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
      <p className="mt-3 text-[10px] text-muted-2">{risk.disclaimer}</p>
    </section>
  );
}
