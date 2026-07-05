"use client";

/**
 * U10 — FillQualityTable: shows slippage vs mid-price for the replay.
 * If no trades were made, renders the honest empty state.
 */

import { type FillQualityStats } from "@/lib/alphaedge-api";

interface FillQualityTableProps {
  fillQuality: FillQualityStats | null;
}

function fmt(n: number, decimals = 4): string {
  return n.toFixed(decimals);
}

function fmtPct(n: number): string {
  return (n * 100).toFixed(3) + "%";
}

export function FillQualityTable({ fillQuality }: FillQualityTableProps) {
  if (!fillQuality || fillQuality.trade_count === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface px-4 py-6 text-center text-sm text-muted-2">
        No trades — edge threshold not met or no snapshots in range
      </div>
    );
  }

  const rows: { label: string; value: string; note?: string }[] = [
    {
      label: "Trade count",
      value: String(fillQuality.trade_count),
      note: "entry trades only",
    },
    {
      label: "Mean slippage",
      value: fmtPct(fillQuality.mean_slippage),
      note: "fill price − mid price (always > 0)",
    },
    {
      label: "Max slippage",
      value: fmtPct(fillQuality.max_slippage),
      note: "worst single fill",
    },
    {
      label: "Total realized P&L",
      value: `$${fmt(fillQuality.total_realized_pnl, 2)}`,
    },
    {
      label: "Mean P&L per trade",
      value: `$${fmt(fillQuality.mean_realized_pnl, 2)}`,
    },
  ];

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[320px] text-sm">
        <thead>
          <tr className="border-b border-border bg-surface">
            <th className="px-4 py-2.5 text-left font-semibold text-muted">Metric</th>
            <th className="px-4 py-2.5 text-right font-semibold text-muted">Value</th>
            <th className="px-4 py-2.5 text-left font-semibold text-muted">Note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-border/40 last:border-0">
              <td className="px-4 py-2.5 text-text">{row.label}</td>
              <td className="px-4 py-2.5 text-right font-mono text-text">{row.value}</td>
              <td className="px-4 py-2.5 text-muted-2">{row.note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
