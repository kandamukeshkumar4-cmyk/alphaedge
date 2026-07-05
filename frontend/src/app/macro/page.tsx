"use client";

// Macro desk (E11) — headline US economic indicators from FRED (or World Bank
// fallback). Read-only context for macro-driven markets (rates, elections,
// economics). Fincept-inspired idea, our own clean-room implementation.
import { useEffect, useState } from "react";
import { fetchMacro, type MacroIndicator } from "@/lib/macro-api";
import { cn } from "@/lib/cn";

function Trend({ change }: { change: number | null }) {
  if (change === null || change === 0) {
    return <span className="font-mono text-xs text-muted-2">—</span>;
  }
  const up = change > 0;
  return (
    <span className={cn("font-mono text-xs font-semibold", up ? "text-primary" : "text-danger")}>
      {up ? "▲" : "▼"} {Math.abs(change).toLocaleString(undefined, { maximumFractionDigits: 2 })}
    </span>
  );
}

function IndicatorCard({ ind }: { ind: MacroIndicator }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{ind.label}</p>
        <Trend change={ind.change} />
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-text">
        {ind.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        <span className="ml-1 text-xs font-normal text-muted-2">{ind.unit}</span>
      </p>
      <p className="mt-1 text-[10px] text-muted-2">
        {ind.date} · {ind.source}
      </p>
    </div>
  );
}

export default function MacroPage() {
  const [data, setData] = useState<MacroIndicator[] | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [source, setSource] = useState<string>("");

  useEffect(() => {
    let dead = false;
    fetchMacro()
      .then((d) => {
        if (dead) return;
        setData(d?.indicators ?? []);
        setSource(d?.source ?? "none");
      })
      .finally(() => {
        if (!dead) setLoaded(true);
      });
    return () => {
      dead = true;
    };
  }, []);

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-6 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">Macro desk</h1>
      <p className="mt-1 text-sm text-muted">
        Headline US economic indicators — the backdrop for rate, election and economics
        markets. {source === "fred" ? "Live from FRED (St. Louis Fed)." : source === "worldbank" ? "From the World Bank open data API." : ""} Research only.
      </p>

      {!loaded ? (
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="rounded-xl border border-border bg-surface p-4">
              <div className="skeleton h-3 w-1/2 rounded" />
              <div className="skeleton mt-3 h-7 w-2/3 rounded" />
            </div>
          ))}
        </div>
      ) : data && data.length > 0 ? (
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((ind) => (
            <IndicatorCard key={ind.key} ind={ind} />
          ))}
        </div>
      ) : (
        <div className="mt-6 rounded-xl border border-border bg-surface p-8 text-center">
          <p className="text-sm font-semibold text-text">Macro data unavailable</p>
          <p className="mx-auto mt-1 max-w-md text-xs text-muted">
            Start the backend to load live economic indicators. FRED data needs a
            (free) <code className="text-accent-bright">FRED_API_KEY</code>; without one it
            falls back to the World Bank open API.
          </p>
        </div>
      )}
    </main>
  );
}
