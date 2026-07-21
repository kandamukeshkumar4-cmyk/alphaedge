"use client";

import { useEffect, useState } from "react";

import { TerminalStepChart } from "@/components/terminal/TerminalStepChart";
import {
  isChartPayload,
  isTablePayload,
  isTextPayload,
  stepSummaryText,
  type ResearchStep,
  type TablePayload,
} from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

type Tab = "summary" | "data" | "chart";

const MAX_TABLE_ROWS = 8;

function looksPnL(value: string | number | null): boolean {
  if (typeof value === "number") return Math.abs(value) >= 100;
  if (typeof value !== "string") return false;
  return /pnl|edge|roi|\$|sim/i.test(value);
}

/** Numeric cells (incl. 12,500 / +0.04 / 0.56 / 48¢) align right in mono. */
function isNumericCell(value: string | number | null): boolean {
  if (typeof value === "number") return true;
  if (typeof value !== "string") return false;
  return /^[+−-]?[$¢]?[\d,]+(\.\d+)?[%¢]?$/.test(value.trim());
}

function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

function StatusGlyph({ status, active }: { status: string; active: boolean }) {
  if (active || status === "running" || status === "pending") {
    return (
      <span
        aria-label="running"
        className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-primary/30 border-t-primary"
      />
    );
  }
  if (status === "failed" || status === "error") {
    // Amber, never danger-red, on this surface.
    return (
      <span
        aria-label="failed"
        className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-gold/15 text-[10px] font-black text-gold"
      >
        !
      </span>
    );
  }
  return (
    <span
      aria-label="complete"
      className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-primary/15 text-primary"
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
        <path
          d="M2 5.2l2 2 4-4.4"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

function StepTable({ table }: { table: TablePayload }) {
  const [showAll, setShowAll] = useState(false);
  const hidden = table.rows.length - MAX_TABLE_ROWS;
  const rows = showAll ? table.rows : table.rows.slice(0, MAX_TABLE_ROWS);
  return (
    <div>
      <div className="max-h-[320px] overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-left text-xs">
          <thead className="font-mono text-[10px] uppercase tracking-wide text-muted">
            <tr>
              {table.columns.map((col) => (
                <th
                  key={col}
                  className="sticky top-0 z-10 bg-surface-2 px-3 py-2 font-semibold"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className="border-t border-border/80 transition-colors hover:bg-surface-2/50"
              >
                {row.map((cell, ci) => {
                  const colName = String(table.columns[ci] ?? "").toLowerCase();
                  const paperish =
                    looksPnL(cell) || colName.includes("edge") || colName.includes("size");
                  const numeric = isNumericCell(cell);
                  return (
                    <td
                      key={ci}
                      className={cn(
                        "px-3 py-2 text-text",
                        numeric && "text-right font-mono tabular-nums",
                      )}
                    >
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
      {hidden > 0 ? (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide text-primary transition hover:bg-primary-dim/60 focus-visible:outline-none active:scale-95"
        >
          {showAll ? "Show less" : `Show all ${table.rows.length} rows (+${hidden})`}
        </button>
      ) : null}
    </div>
  );
}

export function TerminalStepCard({
  step,
  hideSteps,
  active,
  expandNonce,
}: {
  step: ResearchStep;
  /** "Hide steps" stream toggle — collapse every body, keep the numbered rail. */
  hideSteps?: boolean;
  /** Currently-streaming step (spinner + progress sweep). */
  active?: boolean;
  /** Canvas node click: bumping this nonce force-expands the card. */
  expandNonce?: number;
}) {
  const summary = stepSummaryText(step);
  const hasChart = step.kind === "chart" && isChartPayload(step.payload);
  const hasTable = step.kind === "table" && isTablePayload(step.payload);
  const hasText = step.kind === "text" && isTextPayload(step.payload);
  const [tab, setTab] = useState<Tab>("summary");
  const [open, setOpen] = useState(step.sequence <= 2);

  useEffect(() => {
    if (expandNonce) setOpen(true);
  }, [expandNonce]);

  const effectiveOpen = open && !hideSteps;

  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: "summary", label: "Summary", show: true },
    { id: "data", label: "Data", show: hasTable || hasText },
    { id: "chart", label: "Chart", show: hasChart },
  ];

  return (
    <article
      id={`terminal-step-${step.id}`}
      data-testid="terminal-step-card"
      data-step-index={step.sequence}
      className="rounded-xl border border-border bg-surface"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 rounded-t-xl px-4 py-3 text-left transition hover:bg-surface-2/40 focus-visible:outline-none active:bg-surface-2/60"
        aria-expanded={effectiveOpen}
      >
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/15 font-mono text-[11px] font-black text-primary">
          {String(step.sequence).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm font-bold text-text">{step.title}</span>
            <StatusGlyph status={step.status} active={active === true} />
          </span>
          <span className="mt-0.5 block text-xs text-muted line-clamp-2">{summary}</span>
        </span>
        <span className="mt-1 flex shrink-0 items-center gap-2">
          {typeof step.duration_ms === "number" ? (
            <span className="font-mono text-[10px] tabular-nums text-muted-2">
              {formatDuration(step.duration_ms)}
            </span>
          ) : null}
          <span className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
            {step.kind}
          </span>
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            aria-hidden="true"
            className={cn(
              "text-muted-2 transition-transform duration-200",
              effectiveOpen && "rotate-180",
            )}
          >
            <path
              d="M3 4.5l3 3 3-3"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>

      {/* Thin mint progress bar under the running step's header (sweep CSS in
          the motion section: .t-progress). */}
      {active ? (
        <div className="relative h-0.5 overflow-hidden rounded-full bg-primary/10">
          <span className="t-progress absolute inset-y-0 left-0 w-1/3 rounded-full bg-primary" />
        </div>
      ) : null}

      {/* 260ms spring: height auto-animate (grid rows) + scale 0.985→1. */}
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-[260ms] ease-swift",
          effectiveOpen ? "[grid-template-rows:1fr]" : "[grid-template-rows:0fr]",
        )}
      >
        <div className="min-h-0 overflow-hidden">
          <div
            className={cn(
              "border-t border-border px-4 pb-4 pt-2",
              effectiveOpen && "t-card-open",
            )}
          >
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
                      "focus-visible:outline-none active:scale-95",
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
              <StepTable table={step.payload} />
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
        </div>
      </div>
    </article>
  );
}
