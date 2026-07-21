"use client";

import { useState } from "react";

import { TerminalStepChart } from "@/components/terminal/TerminalStepChart";
import {
  isChartPayload,
  isTablePayload,
  isTextPayload,
  stepSummaryText,
  type ResearchStep,
} from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

type Tab = "summary" | "data" | "chart";

function looksPnL(value: string | number | null): boolean {
  if (typeof value === "number") return Math.abs(value) >= 100;
  if (typeof value !== "string") return false;
  return /pnl|edge|roi|\$|sim/i.test(value);
}

export function TerminalStepCard({ step }: { step: ResearchStep }) {
  const summary = stepSummaryText(step);
  const hasChart = step.kind === "chart" && isChartPayload(step.payload);
  const hasTable = step.kind === "table" && isTablePayload(step.payload);
  const hasText = step.kind === "text" && isTextPayload(step.payload);
  const [tab, setTab] = useState<Tab>("summary");
  const [open, setOpen] = useState(step.sequence <= 2);

  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: "summary", label: "Summary", show: true },
    { id: "data", label: "Data", show: hasTable || hasText },
    { id: "chart", label: "Chart", show: hasChart },
  ];

  return (
    <article
      data-testid="terminal-step-card"
      data-step-index={step.sequence}
      className="rounded-xl border border-border bg-surface"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-surface-2/40"
        aria-expanded={open}
      >
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/15 font-mono text-[11px] font-black text-primary">
          {String(step.sequence).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-bold text-text">{step.title}</span>
          <span className="mt-0.5 block text-xs text-muted line-clamp-2">{summary}</span>
        </span>
        <span className="mt-1 font-mono text-[10px] uppercase tracking-wide text-muted-2">
          {step.kind}
        </span>
      </button>

      {open ? (
        <div className="border-t border-border px-4 pb-4 pt-2">
          <div className="mb-3 flex gap-1" role="tablist" aria-label="Step views">
            {tabs
              .filter((t) => t.show)
              .map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "rounded-lg px-2.5 py-1 text-[11px] font-semibold transition",
                    tab === t.id
                      ? "bg-primary/15 text-primary"
                      : "text-muted hover:bg-surface-2 hover:text-text",
                  )}
                >
                  {t.label}
                </button>
              ))}
          </div>

          {tab === "summary" ? (
            <div className="space-y-2">
              <p className="text-sm leading-relaxed text-text">{summary}</p>
              {step.citations.length > 0 ? (
                <ul className="flex flex-wrap gap-1.5">
                  {step.citations.map((c) => (
                    <li
                      key={`${c.source}-${c.label}`}
                      className="rounded border border-border bg-bg/55 px-2 py-0.5 font-mono text-[10px] text-muted"
                    >
                      {c.source}: {c.label}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          {tab === "data" && hasTable && isTablePayload(step.payload) ? (
            (() => {
              const table = step.payload;
              return (
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="min-w-full text-left text-xs">
                    <thead className="bg-surface-2/80 font-mono text-[10px] uppercase tracking-wide text-muted">
                      <tr>
                        {table.columns.map((col) => (
                          <th key={col} className="px-3 py-2 font-semibold">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, ri) => (
                        <tr key={ri} className="border-t border-border/80">
                          {row.map((cell, ci) => {
                            const colName = String(table.columns[ci] ?? "").toLowerCase();
                            const paperish =
                              looksPnL(cell) ||
                              colName.includes("edge") ||
                              colName.includes("size");
                            return (
                              <td key={ci} className="px-3 py-2 text-text">
                                {cell === null || cell === undefined ? "—" : String(cell)}
                                {paperish ? (
                                  <span className="ml-1 text-[9px] font-bold uppercase text-primary">
                                    paper
                                  </span>
                                ) : null}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()
          ) : null}

          {tab === "data" && hasText && isTextPayload(step.payload) ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-text">
              {step.payload.body}
            </p>
          ) : null}

          {tab === "chart" && hasChart && isChartPayload(step.payload) ? (
            <TerminalStepChart payload={step.payload} />
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
