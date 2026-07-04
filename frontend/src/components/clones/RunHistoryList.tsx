"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchCloneRuns, type CloneRun } from "@/lib/alphaedge-api";

interface RunHistoryListProps {
  cloneId: string;
  token: string;
  limit?: number;
}

export function RunHistoryList({ cloneId, token, limit = 5 }: RunHistoryListProps) {
  const [runs, setRuns] = useState<CloneRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchCloneRuns(token, cloneId, limit).then((data) => {
      if (!cancelled) {
        setRuns(data);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [cloneId, token, limit]);

  if (loading) {
    return (
      <div className="space-y-1.5">
        {[1, 2].map((i) => (
          <div key={i} className="h-7 animate-pulse rounded-lg bg-surface-2" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <p className="text-xs text-muted-2">No runs yet — click &quot;Run (paper)&quot; to start.</p>
    );
  }

  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-2">Run history</p>
      {runs.map((run) => (
        <div
          key={run.id}
          className={cn(
            "flex items-center justify-between rounded-lg border px-3 py-1.5 text-xs",
            run.status === "done"
              ? "border-primary/20 bg-primary-dim/50"
              : run.status === "error"
                ? "border-danger/20 bg-danger-dim/50"
                : "border-border bg-surface",
          )}
        >
          <span className="truncate font-mono text-muted">{run.market_slug}</span>
          <div className="ml-3 flex shrink-0 items-center gap-2">
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
                run.status === "done" && "bg-primary/20 text-primary",
                run.status === "error" && "bg-danger/20 text-danger",
                run.status === "running" && "bg-secondary/20 text-secondary",
                run.status === "pending" && "bg-muted/20 text-muted",
              )}
            >
              {run.status}
            </span>
            <span className="text-muted-2">
              {new Date(run.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
