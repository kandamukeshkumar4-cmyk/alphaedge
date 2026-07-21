"use client";

import type { ScoreboardLens } from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

const READ_STYLE: Record<ScoreboardLens["read"], string> = {
  bullish: "text-primary bg-primary/10 border-primary/30",
  bearish: "text-danger bg-danger/10 border-danger/30",
  neutral: "text-muted bg-surface-2 border-border",
  cautious: "text-secondary bg-secondary-dim border-secondary/30",
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

  return (
    <div data-testid="terminal-scoreboard" className="overflow-x-auto rounded-xl border border-border">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">Confluence scoreboard — paper research only</caption>
        <thead className="bg-surface-2/80 font-mono text-[10px] uppercase tracking-wide text-muted">
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
                "border-t border-border",
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
      <p className="border-t border-border px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-primary">
        {verdict?.trim() ? `${verdict.trim()} · ` : ""}
        Paper research · simulated funds · no execution
      </p>
    </div>
  );
}
