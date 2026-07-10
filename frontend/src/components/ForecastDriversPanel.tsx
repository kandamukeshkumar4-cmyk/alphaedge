"use client";

// R02: "Why the model thinks this" — forecast drivers for one market from
// GET /api/v1/markets/{slug}/drivers (backend N02). For/against driver rows with
// family labels + F04 citations, honest {found:false} / empty states. Rendered
// inside the market-detail Intelligence panel. Analysis only — no order path.
import { useEffect, useState } from "react";
import { buildDriversView, fetchDrivers, type DriversView } from "@/lib/drivers-api";
import { SignalEvidenceBlock } from "@/components/SignalEvidence";
import { cn } from "@/lib/cn";

const DIRECTION_TONE: Record<"up" | "down" | "neutral", string> = {
  up: "text-up",
  down: "text-danger",
  neutral: "text-muted",
};

const DIRECTION_BADGE: Record<"up" | "down" | "neutral", string> = {
  up: "border-up/40 bg-up/10 text-up",
  down: "border-danger/40 bg-danger/10 text-danger",
  neutral: "border-border bg-surface-2 text-muted",
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">{children}</p>
  );
}

export function ForecastDriversPanel({ slug }: { slug: string }) {
  const [view, setView] = useState<DriversView | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Fetch-on-load only (no poll loop).
    const ctrl = new AbortController();
    setLoaded(false);
    void fetchDrivers(slug, { signal: ctrl.signal }).then((raw) => {
      setView(buildDriversView(raw));
      setLoaded(true);
    });
    return () => ctrl.abort();
  }, [slug]);

  if (!loaded) {
    return (
      <div className="mt-4">
        <SectionTitle>Why the model thinks this</SectionTitle>
        <div className="skeleton mt-2 h-24 w-full rounded-xl" aria-hidden />
      </div>
    );
  }

  if (!view || !view.found) {
    return (
      <div className="mt-4">
        <SectionTitle>Why the model thinks this</SectionTitle>
        <p className="mt-1.5 text-xs text-muted">
          {view === null || view.slug === ""
            ? "Drivers unreachable — the explanation needs the backend API."
            : "No model probability for this market yet, so there are no drivers to explain — nothing is invented."}
        </p>
      </div>
    );
  }

  return (
    <section className="mt-4" aria-label="Why the model thinks this">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionTitle>Why the model thinks this</SectionTitle>
        {view.gapLabel ? (
          <span
            className={cn(
              "rounded-lg bg-surface-2 px-2 py-0.5 font-mono text-[11px] font-bold",
              DIRECTION_TONE[view.gapTone],
            )}
          >
            model {view.modelLabel} vs market {view.marketLabel} · {view.gapLabel}
          </span>
        ) : null}
      </div>

      {view.hasDrivers ? (
        <ul className="mt-2 space-y-2">
          {view.drivers.map((d, i) => (
            <li key={`${d.label}-${i}`} className="rounded-lg border border-border/60 px-2.5 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-[12px] font-bold text-text">
                  {d.label}
                </span>
                <span
                  className={cn(
                    "shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px] font-black uppercase tracking-[0.04em]",
                    DIRECTION_BADGE[d.directionTone],
                  )}
                >
                  {d.direction}
                </span>
              </div>
              {d.note ? <p className="mt-1 text-[11px] text-muted">{d.note}</p> : null}
              {d.family ? (
                <p className="mt-1 font-mono text-[10px] text-accent">{d.family}</p>
              ) : null}
              {d.evidence ? <SignalEvidenceBlock evidence={d.evidence} /> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1.5 text-xs text-muted-2">
          No individual drivers yet — the model has a probability but no recent
          signal catalysts or a market-price gap to attribute it to.
        </p>
      )}
    </section>
  );
}
