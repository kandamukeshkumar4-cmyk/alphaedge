"use client";

/**
 * Loop V79 (A8) — confluence scoreboard per UI-DIRECTION:
 * 3-col Lens | Read | Why, read pills (bullish=mint, bearish=blue,
 * neutral=gray, cautious=amber), verdict banner above (BULLISH LEAN style,
 * tinted border, never red). Paper research only.
 */

import type { LensRead, ScoreboardLens } from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

const READ_STYLE: Record<LensRead, string> = {
  bullish: "text-primary bg-primary/10 border-primary/30",
  bearish: "text-secondary bg-secondary-dim border-secondary/30",
  neutral: "text-muted bg-surface-2 border-border",
  cautious: "text-amber-300 bg-amber-500/10 border-amber-500/30",
};

/** Majority lean → banner copy like "BULLISH LEAN". Never red. */
function leanBanner(lenses: ScoreboardLens[], verdict?: string | null): {
  label: string;
  tone: "bullish" | "bearish" | "neutral" | "cautious";
} {
  const counts: Record<LensRead, number> = {
    bullish: 0,
    bearish: 0,
    neutral: 0,
    cautious: 0,
  };
  for (const row of lenses) counts[row.read] += 1;

  let tone: LensRead = "neutral";
  let best = -1;
  for (const key of ["bullish", "bearish", "cautious", "neutral"] as const) {
    if (counts[key] > best) {
      best = counts[key];
      tone = key;
    }
  }

  const fromVerdict = verdict?.trim().toLowerCase() ?? "";
  if (fromVerdict.includes("caution") || fromVerdict.includes("cautious"))
    tone = "cautious";
  else if (fromVerdict.includes("bull")) tone = "bullish";
  else if (fromVerdict.includes("bear")) tone = "bearish";
  else if (fromVerdict.includes("neutral")) tone = "neutral";

  const label =
    tone === "bullish"
      ? "BULLISH LEAN"
      : tone === "bearish"
        ? "BEARISH LEAN"
        : tone === "cautious"
          ? "CAUTIOUS LEAN"
          : "NEUTRAL LEAN";

  return { label, tone };
}

const BANNER_TONE: Record<LensRead, string> = {
  bullish: "border-primary/40 bg-primary/8 text-primary",
  bearish: "border-secondary/40 bg-secondary-dim text-secondary",
  neutral: "border-border bg-surface-2 text-muted",
  cautious: "border-amber-500/40 bg-amber-500/10 text-amber-300",
};

export function TerminalScoreboard({
  lenses,
  verdict,
}: {
  lenses: ScoreboardLens[];
  verdict?: string | null;
}) {
  if (lenses.length === 0) {
    return (
      <p className="text-xs text-muted" data-testid="terminal-scoreboard-empty">
        Confluence scoreboard appears when research finishes.
      </p>
    );
  }

  const banner = leanBanner(lenses, verdict);

  return (
    <div data-testid="terminal-scoreboard" className="space-y-3">
      <div
        role="status"
        data-testid="terminal-verdict-banner"
        className={cn(
          "rounded-xl border px-3.5 py-2.5",
          BANNER_TONE[banner.tone],
        )}
      >
        <p className="font-mono text-[11px] font-black uppercase tracking-[0.16em]">
          {banner.label}
        </p>
        {verdict?.trim() ? (
          <p className="mt-1 text-[12px] leading-snug text-text/85">{verdict.trim()}</p>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="min-w-full text-left text-sm">
          <caption className="sr-only">Confluence scoreboard — paper research only</caption>
          <thead className="sticky top-0 bg-surface-2/80 font-mono text-[10px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2">Lens</th>
              <th className="px-3 py-2">Read</th>
              <th className="px-3 py-2">Why</th>
            </tr>
          </thead>
          <tbody>
            {lenses.map((row, i) => (
              <tr
                key={row.lens}
                className={cn(
                  "border-t border-border transition hover:bg-surface-2/50",
                  "t-rise",
                  i === 1 && "t-stagger-1",
                  i === 2 && "t-stagger-2",
                  i === 3 && "t-stagger-3",
                  i === 4 && "t-stagger-4",
                )}
              >
                <td className="px-3 py-2.5 font-semibold capitalize text-text">{row.lens}</td>
                <td className="px-3 py-2.5">
                  <span
                    className={cn(
                      "inline-flex rounded-lg border px-2 py-0.5 font-mono text-[10px] font-bold uppercase",
                      READ_STYLE[row.read],
                    )}
                  >
                    {row.read}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-xs text-muted">{row.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-border px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-muted-2">
          Paper research · simulated funds · no execution
        </p>
      </div>
    </div>
  );
}
