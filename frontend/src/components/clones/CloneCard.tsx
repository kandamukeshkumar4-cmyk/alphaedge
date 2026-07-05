"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import type { CloneConfig, CloneRun } from "@/lib/alphaedge-api";
import { runClone } from "@/lib/alphaedge-api";
import { RunHistoryList } from "./RunHistoryList";

interface CloneCardProps {
  clone: CloneConfig;
  token: string;
  className?: string;
}

export function CloneCard({ clone, token, className }: CloneCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<CloneRun | null>(null);
  const [marketSlug, setMarketSlug] = useState("nba-2025-01-15-lal-bos");

  async function handleRun() {
    if (!marketSlug.trim()) return;
    setRunning(true);
    const result = await runClone(token, clone.clone_id, marketSlug.trim());
    setRunning(false);
    if (result) setLastRun(result);
  }

  return (
    <article
      className={cn(
        "rounded-xl border border-border bg-surface p-4 transition hover:border-accent/40",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-text">{clone.name}</h3>
            <span className="shrink-0 rounded-full border border-border bg-bg px-1.5 py-0.5 text-[10px] font-mono text-muted">
              v{clone.version}
            </span>
            {clone.paper_trading_only && (
              <span className="shrink-0 rounded-full bg-secondary/20 px-1.5 py-0.5 text-[10px] font-semibold text-secondary">
                paper
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-muted">
            Nodes: {clone.nodes.join(" → ")} &middot; edge &ge;{" "}
            {(clone.edge_threshold * 100).toFixed(0)}% &middot; cooldown{" "}
            {clone.cooldown_minutes}m
          </p>
          {clone.markets.length > 0 && (
            <p className="mt-0.5 truncate text-[11px] text-muted-2">
              Watching: {clone.markets.slice(0, 3).join(", ")}
              {clone.markets.length > 3 && ` +${clone.markets.length - 3} more`}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 rounded-lg p-1 text-muted hover:text-text"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <ChevronIcon open={expanded} />
        </button>
      </div>

      {/* Run panel */}
      {expanded && (
        <div className="mt-4 space-y-3 border-t border-border pt-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={marketSlug}
              onChange={(e) => setMarketSlug(e.target.value)}
              placeholder="Market slug…"
              className="flex-1 rounded-lg border border-border bg-bg px-3 py-1.5 text-xs text-text placeholder:text-muted-2 focus:border-accent focus:outline-none"
            />
            <button
              type="button"
              onClick={handleRun}
              disabled={running}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                running
                  ? "cursor-not-allowed bg-surface text-muted"
                  : "bg-accent-bright text-bg hover:bg-accent",
              )}
            >
              {running ? "Running…" : "Run (paper)"}
            </button>
          </div>

          {lastRun && (
            <div
              className={cn(
                "rounded-lg px-3 py-2 text-xs",
                lastRun.status === "done"
                  ? "bg-primary-dim text-primary"
                  : "bg-danger-dim text-danger",
              )}
            >
              <span className="font-semibold">
                {lastRun.status === "done" ? "Done" : "Error"}
              </span>{" "}
              &middot; {lastRun.trace.length} steps traced
              {lastRun.status === "error" && lastRun.error && (
                <span className="ml-1 text-muted-2">— {lastRun.error.slice(0, 80)}</span>
              )}
            </div>
          )}

          <RunHistoryList cloneId={clone.clone_id} token={token} />
        </div>
      )}
    </article>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={cn("transition-transform", open && "rotate-180")}
    >
      <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
