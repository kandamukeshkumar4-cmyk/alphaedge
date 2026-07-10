"use client";

// R03: model-vs-market edge history — a small inline-SVG chart (TrackRecord
// style) from GET /api/v1/markets/{slug}/edge-history (backend N03). Two lines
// on a fixed 0..100% y-axis (model P(YES) vs market-implied P(YES)); the SIGNED
// latest edge is labelled. role=img + <title>/<desc> for a11y. Honest empties;
// reduced-motion-safe (AnimatedNumber jumps instantly). Analysis only.
import { useEffect, useState } from "react";
import {
  buildEdgeHistoryView,
  buildLinePath,
  fetchEdgeHistory,
  type EdgeHistoryView,
} from "@/lib/edge-history-api";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { cn } from "@/lib/cn";

const EDGE_TONE: Record<"up" | "down" | "neutral", string> = {
  up: "text-up",
  down: "text-danger",
  neutral: "text-muted",
};

const W = 320;
const H = 140;
const PAD = 16;

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">{children}</p>
  );
}

function Chart({ view }: { view: EdgeHistoryView }) {
  const modelPath = buildLinePath(
    view.points.map((p) => p.modelP),
    { width: W, height: H, pad: PAD },
  );
  const marketPath = buildLinePath(
    view.points.map((p) => p.marketP),
    { width: W, height: H, pad: PAD },
  );
  const desc = `Model probability versus market-implied probability over the ${view.windowLabel} window across ${view.count} points. Latest model ${view.latest?.modelLabel ?? "n/a"}, market ${view.latest?.marketLabel ?? "n/a"}, edge ${view.latest?.edgeLabel ?? "n/a"}.`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Model vs market edge history over ${view.windowLabel}`}
    >
      <title>Model vs market edge history over {view.windowLabel}</title>
      <desc>{desc}</desc>
      {/* baseline + mid gridline (50%) */}
      <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} className="stroke-border" strokeWidth={1} />
      <line
        x1={PAD}
        y1={PAD + (H - PAD * 2) / 2}
        x2={W - PAD}
        y2={PAD + (H - PAD * 2) / 2}
        className="stroke-border/50"
        strokeWidth={1}
        strokeDasharray="3 4"
      />
      {view.hasMarketLine ? (
        <path
          d={marketPath}
          className="fill-none stroke-muted-2"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : null}
      <path
        d={modelPath}
        className="fill-none stroke-primary"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <text x={PAD} y={PAD - 5} className="fill-muted-2 text-[8px]">
        100%
      </text>
      <text x={PAD} y={H - PAD + 9} className="fill-muted-2 text-[8px]">
        0%
      </text>
    </svg>
  );
}

export function EdgeHistoryChart({ slug }: { slug: string }) {
  const [view, setView] = useState<EdgeHistoryView | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Fetch-on-load only (no poll loop).
    const ctrl = new AbortController();
    setLoaded(false);
    void fetchEdgeHistory(slug, { signal: ctrl.signal }).then((raw) => {
      setView(buildEdgeHistoryView(raw));
      setLoaded(true);
    });
    return () => ctrl.abort();
  }, [slug]);

  if (!loaded) {
    return (
      <div className="mt-4">
        <SectionTitle>Model vs market history</SectionTitle>
        <div className="skeleton mt-2 h-32 w-full rounded-xl" aria-hidden />
      </div>
    );
  }

  if (!view || !view.found || !view.available) {
    return (
      <div className="mt-4">
        <SectionTitle>Model vs market history</SectionTitle>
        <p className="mt-1.5 text-xs text-muted">
          {view === null || view.slug === ""
            ? "Edge history unreachable — the chart needs the backend API."
            : view.found && view.count === 1
              ? "Only one prediction logged so far — a trend line appears once there are at least two points."
              : "No prediction history for this market yet — the chart plots real logged predictions only."}
        </p>
      </div>
    );
  }

  const last = view.points[view.points.length - 1];

  return (
    <section className="mt-4" aria-label="Model vs market edge history">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionTitle>Model vs market history</SectionTitle>
        {view.latest?.edgeLabel ? (
          <span
            className={cn(
              "rounded-lg bg-surface-2 px-2 py-0.5 font-mono text-[11px] font-bold",
              EDGE_TONE[view.latest.edgeTone],
            )}
          >
            edge{" "}
            <AnimatedNumber
              value={last.edge ?? 0}
              format={(v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)} pts`}
            />
          </span>
        ) : null}
      </div>

      <div className="mt-2 rounded-xl border border-border/60 bg-surface-2/30 p-2">
        <Chart view={view} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 rounded-full bg-primary" aria-hidden />
          model {view.latest?.modelLabel ?? "—"}
        </span>
        {view.hasMarketLine ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 rounded-full bg-muted-2" aria-hidden />
            market {view.latest?.marketLabel ?? "—"}
          </span>
        ) : (
          <span>no market snapshot in window</span>
        )}
        <span>
          {view.count} pts · {view.windowLabel}
        </span>
      </div>
    </section>
  );
}
