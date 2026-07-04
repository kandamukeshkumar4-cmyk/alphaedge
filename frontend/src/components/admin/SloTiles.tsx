"use client";

// U12 — Latency SLO tiles.
// Sourced from the existing Prometheus metrics (stream latency + brief latency).
// Honest unavailable state: p50/p95/p99 are null when no data observed yet.

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchSloTiles, type SloTile } from "@/lib/observability-api";

export function SloTiles() {
  const [tiles, setTiles] = useState<SloTile[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const data = await fetchSloTiles();
    setTiles(data.tiles);
    setLoading(false);
  };

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 30_000);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text">Latency SLOs</h2>
          <p className="text-xs text-muted">
            p50 / p95 / p99 from in-process Prometheus histograms.
          </p>
        </div>
        <button
          className="rounded border border-border-light px-3 py-1 text-xs font-semibold text-text transition hover:border-primary hover:text-primary disabled:opacity-50"
          disabled={loading}
          onClick={() => void load()}
          type="button"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {loading ? (
        <p className="p-4 text-sm text-muted">Loading SLO data…</p>
      ) : tiles.length === 0 ? (
        <p className="p-4 text-sm text-muted">SLO data unavailable — backend not reachable.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
          {tiles.map((tile) => (
            <SloTileCard key={tile.name} tile={tile} />
          ))}
        </div>
      )}
    </section>
  );
}

function SloTileCard({ tile }: { tile: SloTile }) {
  const hasData = tile.p99 != null;
  const sloMet = tile.slo_met;

  return (
    <div
      className={cn(
        "rounded-xl border p-4 space-y-3",
        sloMet === true
          ? "border-up/40 bg-up/5"
          : sloMet === false
            ? "border-danger/40 bg-danger-dim"
            : "border-border bg-surface-2",
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold text-text">{tile.name}</p>
          <p className="text-xs text-muted">
            SLO target: {tile.slo_ms.toFixed(0)} {tile.unit}
          </p>
        </div>
        <SloStatusBadge met={sloMet} hasData={hasData} />
      </div>

      {hasData ? (
        <div className="grid grid-cols-3 gap-2">
          <PercentileTile label="p50" value={tile.p50} unit={tile.unit} />
          <PercentileTile label="p95" value={tile.p95} unit={tile.unit} />
          <PercentileTile
            label="p99"
            value={tile.p99}
            unit={tile.unit}
            highlight={sloMet === false}
          />
        </div>
      ) : (
        <p className="text-xs text-muted italic">
          No observations yet — data appears once stream events flow through this process.
        </p>
      )}
    </div>
  );
}

function PercentileTile({
  label,
  value,
  unit,
  highlight = false,
}: {
  label: string;
  value: number | null;
  unit: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border/50 bg-bg/60 p-2 text-center">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-2">{label}</p>
      <p
        className={cn(
          "mt-0.5 text-base font-bold tabular-nums",
          highlight ? "text-danger" : "text-text",
        )}
      >
        {value != null ? value.toFixed(1) : "—"}
      </p>
      <p className="text-[10px] text-muted">{unit}</p>
    </div>
  );
}

function SloStatusBadge({
  met,
  hasData,
}: {
  met: boolean | null;
  hasData: boolean;
}) {
  if (!hasData) {
    return (
      <span className="rounded border border-muted-2/40 bg-surface px-2 py-0.5 text-[10px] font-semibold text-muted-2">
        no data
      </span>
    );
  }
  if (met === true) {
    return (
      <span className="rounded border border-up/40 bg-up/10 px-2 py-0.5 text-[10px] font-semibold text-up">
        MET
      </span>
    );
  }
  return (
    <span className="rounded border border-danger/40 bg-danger-dim px-2 py-0.5 text-[10px] font-semibold text-danger">
      BREACHED
    </span>
  );
}
