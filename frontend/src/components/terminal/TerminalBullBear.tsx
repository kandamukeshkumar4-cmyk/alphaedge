"use client";

/**
 * Loop V79 (A8) — bull/bear cases per UI-DIRECTION: stacked sections
 * "The bull case" / "The bear case" with numbered bold-lead sentences.
 * Bear case uses blue (never danger-red). Paper research only.
 */

import { cn } from "@/lib/cn";

/** Split prose into numbered leads — first clause/sentence is bold. */
function parseLeads(text: string): { lead: string; rest: string }[] {
  const raw = text.trim();
  if (!raw) return [];

  // Prefer explicit numbered lines ("1. …", "2) …") then sentence splits.
  const numbered = raw
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^\d+[.)]\s*/, "").trim())
    .filter(Boolean);

  const parts =
    numbered.length > 1
      ? numbered
      : raw
          .split(/(?<=[.!?])\s+/)
          .map((s) => s.trim())
          .filter(Boolean);

  return parts.map((sentence) => {
    const m = sentence.match(/^([^—:.,!?]+(?:\s+[^—:.,!?]{0,40})?)([—:,.!?\s].*)?$/);
    if (m && m[2]) {
      return { lead: m[1].trim(), rest: m[2].replace(/^[\s—:,]+/, " ").trimStart() };
    }
    const words = sentence.split(/\s+/);
    if (words.length > 8) {
      return {
        lead: words.slice(0, 5).join(" "),
        rest: words.slice(5).join(" "),
      };
    }
    return { lead: sentence, rest: "" };
  });
}

function CaseBlock({
  title,
  body,
  tone,
}: {
  title: string;
  body: string;
  tone: "bull" | "bear";
}) {
  const items = parseLeads(body);
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        tone === "bull"
          ? "border-primary/25 bg-primary-dim/20"
          : "border-secondary/30 bg-secondary-dim/40",
      )}
    >
      <h3
        className={cn(
          "text-[11px] font-black uppercase tracking-[0.12em]",
          tone === "bull" ? "text-primary" : "text-secondary",
        )}
      >
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No case yet.</p>
      ) : (
        <ol className="mt-3 space-y-2.5">
          {items.map((item, i) => (
            <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-text">
              <span
                className={cn(
                  "mt-0.5 font-mono text-[11px] font-bold tabular-nums",
                  tone === "bull" ? "text-primary" : "text-secondary",
                )}
              >
                {i + 1}.
              </span>
              <span>
                <strong className="font-bold text-text">{item.lead}</strong>
                {item.rest ? (
                  <span className="text-muted">
                    {item.rest.startsWith(".") || item.rest.startsWith("!") || item.rest.startsWith("?")
                      ? item.rest
                      : ` ${item.rest}`}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3 text-[10px] text-muted-2">
        Paper research only — simulated funds · no execution.
      </p>
    </div>
  );
}

export function TerminalBullBear({
  bullCase,
  bearCase,
}: {
  bullCase?: string | null;
  bearCase?: string | null;
}) {
  if (!bullCase && !bearCase) return null;

  return (
    <section
      aria-label="Bull and bear cases"
      data-testid="terminal-bull-bear"
      className="grid gap-3"
    >
      {bullCase ? (
        <CaseBlock title="The bull case" body={bullCase} tone="bull" />
      ) : null}
      {bearCase ? (
        <CaseBlock title="The bear case" body={bearCase} tone="bear" />
      ) : null}
    </section>
  );
}
