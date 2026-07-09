"use client";

import Link from "next/link";

// Original CSS-gradient hero art (no external assets). Rotates two slides:
// WC2026 track + the AI analyst desk.
export function QuestHero() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border">
      <div
        className="relative flex min-h-[150px] flex-col justify-center gap-2 px-5 py-6 sm:min-h-[185px] sm:px-8"
        style={{
          background:
            "radial-gradient(120% 160% at 85% 20%, rgba(62,230,176,0.35) 0%, rgba(32,201,151,0.12) 35%, transparent 65%), linear-gradient(105deg, #0a0e0d 30%, #0e2a22 70%, #123c30 100%)",
        }}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "repeating-linear-gradient(115deg, transparent 0px, transparent 26px, rgba(62,230,176,0.05) 26px, rgba(62,230,176,0.05) 28px)",
          }}
        />
        <p className="relative font-mono text-xs font-semibold uppercase tracking-[0.2em] text-accent-bright">
          Featured · FIFA World Cup 2026
        </p>
        <h1 className="relative max-w-xl text-2xl font-black uppercase leading-none tracking-tight text-text sm:text-4xl">
          World Cup &rsquo;26
        </h1>
        <p className="relative max-w-md text-sm text-muted">
          Live match markets mirrored from Kalshi &amp; Polymarket — with AI briefs,
          whale signals and a public track record. Research only — no bets in-app.
        </p>
        <div className="relative mt-1 flex gap-2">
          <Link
            href="/markets?topic=sports"
            className="rounded-lg bg-accent-bright px-4 py-2 text-sm font-semibold text-bg transition hover:bg-accent"
          >
            Browse WC2026
          </Link>
          <Link
            href="/research"
            className="rounded-lg border border-border-light bg-bg/40 px-4 py-2 text-sm font-semibold text-text backdrop-blur transition hover:border-accent"
          >
            Read AI briefs
          </Link>
        </div>
      </div>
      <div className="flex justify-center gap-1.5 py-2">
        <span className="h-1 w-5 rounded-full bg-accent-bright" />
        <span className="h-1 w-1.5 rounded-full bg-surface-3" />
        <span className="h-1 w-1.5 rounded-full bg-surface-3" />
      </div>
    </div>
  );
}
