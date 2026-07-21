"use client";

import type { SessionSummary } from "@/lib/terminal-api";
import { cn } from "@/lib/cn";

export function TerminalSessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  loading,
}: {
  sessions: SessionSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  loading?: boolean;
}) {
  return (
    <aside
      data-testid="terminal-session-sidebar"
      className="flex h-full min-h-0 flex-col rounded-xl border border-border bg-surface"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2.5">
        <h2 className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-muted">
          Sessions
        </h2>
        <button
          type="button"
          onClick={onNew}
          data-testid="terminal-new-session"
          className="rounded-lg bg-primary px-2.5 py-1 text-[11px] font-bold text-bg shadow-glow transition hover:brightness-110"
        >
          New
        </button>
      </div>
      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {loading ? (
          <li className="px-2 py-3 text-xs text-muted">Loading…</li>
        ) : sessions.length === 0 ? (
          <li className="px-2 py-3 text-xs text-muted">No saved sessions yet.</li>
        ) : (
          sessions.map((s) => {
            const active = s.id === activeId;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onSelect(s.id)}
                  className={cn(
                    "w-full rounded-lg px-2.5 py-2 text-left transition",
                    active
                      ? "border border-primary/40 bg-primary-dim/50"
                      : "border border-transparent hover:bg-surface-2/70",
                  )}
                >
                  <span className="line-clamp-2 text-[12px] font-semibold text-text">
                    {s.question}
                  </span>
                  <span className="mt-1 flex items-center gap-2 font-mono text-[10px] text-muted-2">
                    <span className="uppercase">{s.status}</span>
                    <span>·</span>
                    <span>{s.step_count} steps</span>
                  </span>
                </button>
              </li>
            );
          })
        )}
      </ul>
    </aside>
  );
}
