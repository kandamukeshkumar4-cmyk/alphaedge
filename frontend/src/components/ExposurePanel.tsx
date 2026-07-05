"use client";

/**
 * ExposurePanel — U04 portfolio exposure analysis.
 *
 * Shows open notional grouped by correlated underlier as horizontal bars,
 * concentration secondarys when any single underlier exceeds 40 % of book,
 * and a clean "No concentration risk" state for a flat/empty book.
 *
 * Data: fetched from GET /api/v1/portfolio/exposure (read-only, no order
 * surface). Math is deterministic (see backend/app/services/exposure_service.py).
 */

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  fetchPortfolioExposure,
  type ExposureGroup,
  type PortfolioExposure,
} from "@/lib/portfolio-api";
import { ConcentrationWarning } from "@/components/ConcentrationWarning";

type Props = {
  token: string;
};

export function ExposurePanel({ token }: Props) {
  const [data, setData] = useState<PortfolioExposure | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchPortfolioExposure(token)
      .then((result) => setData(result))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">
          Exposure Analysis
        </p>
        <div className="mt-3 space-y-2">
          <div className="skeleton h-5 w-full rounded" />
          <div className="skeleton h-5 w-4/5 rounded" />
          <div className="skeleton h-5 w-3/5 rounded" />
        </div>
      </section>
    );
  }

  if (!data) return null;

  const isEmpty = data.groups.length === 0;

  return (
    <section
      className="mb-6 rounded-2xl border border-border bg-surface p-5"
      aria-label="Exposure analysis"
    >
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">
            Exposure Analysis
          </p>
          <p className="mt-0.5 text-sm text-muted">
            Open positions grouped by correlated underlier
          </p>
        </div>
        {data.total_open_notional > 0 ? (
          <span className="font-mono text-sm font-bold text-text">
            ${data.total_open_notional.toFixed(2)} total notional
          </span>
        ) : null}
      </div>

      {/* Concentration secondarys */}
      {data.has_concentration && data.groups.length > 0 ? (
        <div className="mb-4 space-y-2">
          {data.groups
            .filter((g) => g.concentrated)
            .map((g) => (
              <ConcentrationWarning
                key={g.underlier}
                underlier={g.underlier}
                pctOfTotal={g.pct_of_total}
                positionCount={g.position_count}
                netDirectional={g.net_directional}
              />
            ))}
        </div>
      ) : null}

      {/* Empty / flat book */}
      {isEmpty ? (
        <div className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-text">
          <span className="text-primary" aria-hidden>
            ✓
          </span>
          <span>No concentration risk — book is flat or empty.</span>
        </div>
      ) : (
        <div className="space-y-3">
          {data.groups.map((group) => (
            <ExposureBar
              key={group.underlier}
              group={group}
              totalNotional={data.total_open_notional}
            />
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <p className="mt-4 text-[11px] leading-relaxed text-muted">
        {data.disclaimer}
      </p>
    </section>
  );
}

function ExposureBar({
  group,
  totalNotional,
}: {
  group: ExposureGroup;
  totalNotional: number;
}) {
  const pct = totalNotional > 0 ? group.pct_of_total : 0;
  const isLong = group.net_directional >= 0;

  return (
    <div>
      {/* Label row */}
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={cn(
              "shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase",
              isLong ? "bg-primary-dim text-primary" : "bg-danger-dim text-danger",
            )}
          >
            {isLong ? "LONG" : "SHORT"}
          </span>
          <span className="truncate text-sm font-semibold text-text">
            {group.underlier}
          </span>
          {group.concentrated ? (
            <span className="shrink-0 rounded border border-secondary/40 bg-secondary/10 px-1.5 py-0.5 text-[10px] font-bold text-secondary">
              CONCENTRATED
            </span>
          ) : null}
        </div>
        <div className="shrink-0 text-right">
          <span className="font-mono text-sm font-bold text-text">
            {pct.toFixed(1)}%
          </span>
          <span className="ml-1 text-[11px] text-muted">
            ${group.total_notional.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 overflow-hidden rounded-full bg-border">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            group.concentrated
              ? "bg-secondary"
              : isLong
                ? "bg-primary"
                : "bg-danger",
          )}
          style={{ width: `${Math.min(pct, 100)}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${group.underlier} exposure`}
        />
      </div>

      {/* Sub-row: position slugs */}
      {group.positions.length > 0 ? (
        <p className="mt-0.5 truncate text-[11px] text-muted">
          {group.positions.slice(0, 3).join(" · ")}
          {group.positions.length > 3
            ? ` +${group.positions.length - 3} more`
            : ""}
        </p>
      ) : null}
    </div>
  );
}
