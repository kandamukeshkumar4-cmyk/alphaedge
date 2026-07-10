"use client";

// X02 — realized CLV summary panel (backend K02). Consumes
// GET /api/v1/portfolio/clv-summary (authed): distribution histogram +
// positive-share + mean + count. Honest empty ("no settled paper trades yet")
// and anon ("sign in to see your CLV"). Read-only, paper trading only — a CLV
// readout never places a trade. Fetch-once on token change (no poll loop).
import Link from "next/link";
import { useEffect, useState } from "react";

import { AnimatedNumber } from "@/components/AnimatedNumber";
import { cn } from "@/lib/cn";
import {
  buildClvSummaryView,
  fetchPortfolioClvSummary,
  type ClvSummaryView,
} from "@/lib/portfolio-clv-api";

const TONE_TEXT: Record<"up" | "down" | "neutral", string> = {
  up: "text-primary",
  down: "text-danger",
  neutral: "text-text",
};

const TONE_BAR: Record<"up" | "down" | "neutral", string> = {
  up: "bg-primary",
  down: "bg-danger",
  neutral: "bg-muted-2",
};

function Histogram({ view }: { view: ClvSummaryView }) {
  return (
    <div
      className="mt-4 grid grid-cols-6 items-end gap-1.5"
      role="img"
      aria-label={`Realized CLV distribution across ${view.count} settled paper trades: ${view.bars
        .map((b) => `${b.label} ${b.count}`)
        .join(", ")}`}
    >
      {view.bars.map((bar) => (
        <div key={bar.label} className="flex flex-col items-center gap-1">
          <span className="font-mono text-[10px] font-bold text-muted-2">{bar.count}</span>
          <div className="flex h-24 w-full items-end rounded bg-surface-2/60" aria-hidden>
            <div
              className={cn("w-full rounded-t", TONE_BAR[bar.tone])}
              style={{ height: `${Math.max(bar.fraction * 100, bar.count > 0 ? 6 : 0)}%` }}
            />
          </div>
          <span className="text-center text-[8px] leading-tight text-muted-2">{bar.label}</span>
        </div>
      ))}
    </div>
  );
}

function Tile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  tone?: "up" | "down" | "neutral";
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/50 px-3.5 py-2.5">
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">{label}</p>
      <p className={cn("mt-1 font-mono text-xl font-black", TONE_TEXT[tone])}>{value}</p>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <section aria-label="Closing-line value" className="mb-6 rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-black tracking-tight text-text">Closing-line value (CLV)</h2>
        <span className="rounded-pill border border-border px-2 py-0.5 font-mono text-[10px] font-semibold text-muted-2">
          SETTLED PAPER TRADES
        </span>
      </div>
      {children}
    </section>
  );
}

export function PortfolioClvPanel({ token }: { token: string | null }) {
  const [view, setView] = useState<ClvSummaryView | null>(null);

  useEffect(() => {
    if (!token) {
      setView(null);
      return;
    }
    let dead = false;
    const ctrl = new AbortController();
    setView(null);
    void fetchPortfolioClvSummary(token, ctrl.signal).then((raw) => {
      if (!dead) setView(buildClvSummaryView(raw));
    });
    return () => {
      dead = true;
      ctrl.abort();
    };
  }, [token]);

  // Anon — the panel is self-contained so it honours the sign-in state even if
  // the page did not redirect.
  if (!token) {
    return (
      <Shell>
        <p className="mt-2 text-sm text-muted">
          Sign in to see your CLV — the realized edge of your paper entries versus each market&apos;s
          closing line.
        </p>
        <Link
          href="/auth/login?next=/portfolio"
          className="mt-3 inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
        >
          Sign in
        </Link>
      </Shell>
    );
  }

  if (view === null) {
    return (
      <Shell>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-16 rounded-xl" />
          ))}
        </div>
        <div className="skeleton mt-4 h-24 w-full rounded" />
      </Shell>
    );
  }

  if (!view.reachable) {
    return (
      <Shell>
        <p className="mt-2 text-sm text-muted">
          Your CLV summary is unavailable right now — the live API did not answer. Nothing is
          fabricated; try refreshing.
        </p>
      </Shell>
    );
  }

  if (!view.available) {
    return (
      <Shell>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted">{view.emptyMessage}</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile
          label="Settled scored"
          value={
            <AnimatedNumber value={view.count} format={(n) => String(Math.round(n))} />
          }
        />
        <Tile
          label="Positive share"
          value={
            view.positiveShareValue === null ? (
              "—"
            ) : (
              <AnimatedNumber
                value={view.positiveShareValue}
                format={(n) => `${Math.round(n * 100)}%`}
              />
            )
          }
          tone={view.positiveShareValue !== null && view.positiveShareValue >= 0.5 ? "up" : "neutral"}
        />
        <Tile
          label="Mean CLV"
          value={
            view.meanValue === null ? (
              "—"
            ) : (
              <AnimatedNumber
                value={view.meanValue}
                format={(n) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)} pts`}
              />
            )
          }
          tone={view.meanTone}
        />
      </div>

      <Histogram view={view} />

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-2">
        <span>
          Total CLV <span className={cn("font-mono font-semibold", TONE_TEXT[view.totalClvTone])}>{view.totalClvLabel}</span>
        </span>
        <span>
          {view.matchedSlugs} market{view.matchedSlugs === 1 ? "" : "s"} matched · {view.settledOrders} settled order
          {view.settledOrders === 1 ? "" : "s"}
        </span>
      </div>

      <p className="mt-3 text-[10px] leading-relaxed text-muted-2">{view.disclaimer}</p>
    </Shell>
  );
}
