"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import {
  fetchAdminMarkets,
  type AdminMarketRow,
} from "@/lib/admin-dashboard-api";

type MarketFilter = "all" | "wc2026" | "resolved";

type AdminMarketsTableProps = {
  apiKey: string;
};

const STATUS_ORDER: Record<string, number> = {
  open: 0,
  locked: 1,
  resolved: 2,
};

export function AdminMarketsTable({ apiKey }: AdminMarketsTableProps) {
  const [markets, setMarkets] = useState<AdminMarketRow[]>([]);
  const [filter, setFilter] = useState<MarketFilter>("all");
  const [sortAsc, setSortAsc] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMarkets = useCallback(async () => {
    if (!apiKey.trim()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const result = await fetchAdminMarkets(apiKey, {
      limit: 200,
      tournamentTag: filter === "wc2026" ? "wc2026" : undefined,
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setMarkets([]);
      return;
    }
    setMarkets(result.data);
  }, [apiKey, filter]);

  useEffect(() => {
    void loadMarkets();
  }, [loadMarkets]);

  const displayed = useMemo(() => {
    let rows = markets;
    if (filter === "resolved") {
      rows = rows.filter((row) => row.status === "resolved");
    }
    return [...rows].sort((a, b) => {
      const diff = (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99);
      return sortAsc ? diff : -diff;
    });
  }, [markets, filter, sortAsc]);

  return (
    <section className="rounded-xl border border-border bg-surface" id="markets">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold text-text">Markets</h2>
        <div className="flex flex-wrap gap-2">
          {(["all", "wc2026", "resolved"] as const).map((chip) => (
            <button
              key={chip}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-semibold transition",
                filter === chip
                  ? "border-primary/45 bg-primary-dim text-primary"
                  : "border-border text-muted hover:border-primary hover:text-primary",
              )}
              onClick={() => setFilter(chip)}
              type="button"
            >
              {chip === "all" ? "All" : chip === "wc2026" ? "WC2026" : "Resolved"}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p className="p-4 text-sm text-danger">{error}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-border bg-surface-2 text-xs uppercase text-muted-2">
              <tr>
                <th className="px-4 py-3 font-semibold">Slug</th>
                <th className="px-4 py-3 font-semibold">Title</th>
                <th className="px-4 py-3 font-semibold">
                  <button
                    className="inline-flex items-center gap-1 font-semibold uppercase hover:text-primary"
                    onClick={() => setSortAsc((value) => !value)}
                    type="button"
                  >
                    Status {sortAsc ? "↑" : "↓"}
                  </button>
                </th>
                <th className="px-4 py-3 font-semibold">Category</th>
                <th className="px-4 py-3 font-semibold">Tournament</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td className="px-4 py-8 text-center text-muted" colSpan={5}>
                    Loading markets…
                  </td>
                </tr>
              ) : displayed.length ? (
                displayed.map((market) => (
                  <tr key={market.slug}>
                    <td className="px-4 py-3 font-mono text-xs text-muted-2">
                      {market.slug}
                    </td>
                    <td className="px-4 py-3 text-text">{market.title}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={market.status} />
                    </td>
                    <td className="px-4 py-3 text-muted">{market.category}</td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-2">
                      {market.tournament_tag ?? "—"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center text-muted" colSpan={5}>
                    No markets found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const classes =
    status === "resolved"
      ? "border-muted/45 bg-surface-2 text-muted"
      : status === "locked"
        ? "border-accent/45 bg-accent/10 text-accent"
        : "border-primary/45 bg-primary-dim text-primary";

  return (
    <span className={cn("inline-flex rounded border px-2 py-1 text-xs font-semibold", classes)}>
      {status}
    </span>
  );
}
