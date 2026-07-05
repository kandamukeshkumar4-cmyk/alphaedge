"use client";

// Weather edge desk (S01) — free NWS point forecasts priced through a
// Gaussian-bucket model against live Kalshi daily-high ladders. Informational
// edges only: nothing here (or server-side) can place an order.
import { useEffect, useState } from "react";
import { fetchWeatherEdges, type WeatherCityReport, type WeatherBucket } from "@/lib/weather-api";
import { cn } from "@/lib/cn";

function pct(v: number | null): string {
  if (v === null) return "—";
  return `${Math.round(v * 100)}%`;
}

function BucketRow({ bucket }: { bucket: WeatherBucket }) {
  const model = Math.max(0, Math.min(1, bucket.model_probability));
  const market = bucket.market_yes === null ? null : Math.max(0, Math.min(1, bucket.market_yes));
  const underpriced = bucket.read === "yes-underpriced";
  return (
    <div className="grid grid-cols-[minmax(72px,1fr)_2fr_auto] items-center gap-3 py-1.5">
      <span className="font-mono text-xs text-text">{bucket.bucket}</span>
      <div className="relative h-4 overflow-hidden rounded bg-surface-2">
        <div
          className="absolute inset-y-0 left-0 rounded bg-accent-bright/30"
          style={{ width: `${model * 100}%` }}
          aria-hidden
        />
        {market !== null && (
          <div
            className="absolute inset-y-0 w-0.5 bg-text/70"
            style={{ left: `${market * 100}%` }}
            title={`market ${pct(market)}`}
            aria-hidden
          />
        )}
      </div>
      <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums">
        <span className="text-muted">m {pct(model)}</span>
        <span className="text-muted-2">vs {pct(market)}</span>
        {bucket.edge !== null && (
          <span
            className={cn(
              "rounded px-1.5 py-0.5 font-semibold",
              underpriced ? "bg-primary/15 text-primary" : "bg-danger/15 text-danger",
            )}
          >
            {bucket.edge > 0 ? "+" : ""}
            {(bucket.edge * 100).toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}

function CityCard({ report }: { report: WeatherCityReport }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-text">{report.city}</p>
        <p className="font-mono text-xs text-muted">
          NWS high <span className="text-lg font-semibold text-accent-bright">{report.forecast_high_f}°F</span>
        </p>
      </div>
      <p className="mt-0.5 text-[10px] text-muted-2">
        {report.series_ticker} · σ {report.sigma_f}°F · {report.source}
      </p>
      <div className="mt-3 divide-y divide-border/50">
        {report.buckets.map((b) => (
          <BucketRow key={b.ticker} bucket={b} />
        ))}
      </div>
    </div>
  );
}

export default function WeatherPage() {
  const [data, setData] = useState<WeatherCityReport[] | null>(null);
  const [date, setDate] = useState<string>("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    fetchWeatherEdges()
      .then((d) => {
        if (dead) return;
        setData(d?.cities ?? []);
        setDate(d?.date ?? "");
      })
      .finally(() => {
        if (!dead) setLoaded(true);
      });
    return () => {
      dead = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-[1100px] px-4 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-bold text-text">Weather edge desk</h1>
        {date && <p className="font-mono text-xs text-muted">settle date {date}</p>}
      </div>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        Free NWS government forecasts priced through a Gaussian-bucket model against live Kalshi
        daily-high ladders. Bars show model probability; the tick marks the market price. Positive
        edge = model thinks YES is underpriced. Paper research only — never an order.
      </p>

      {!loaded && (
        <div className="mt-6 grid gap-4 md:grid-cols-2" aria-busy>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl border border-border bg-surface" />
          ))}
        </div>
      )}

      {loaded && (data?.length ?? 0) === 0 && (
        <div className="mt-6 rounded-xl border border-border bg-surface p-6 text-sm text-muted">
          No weather ladders priced right now. The desk needs the backend online plus open Kalshi
          daily-high markets for tomorrow — check back shortly.
        </div>
      )}

      {loaded && data && data.length > 0 && (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {data.map((report) => (
            <CityCard key={report.series_ticker} report={report} />
          ))}
        </div>
      )}
    </main>
  );
}
