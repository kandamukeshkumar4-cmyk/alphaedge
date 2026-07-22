"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { TERMINAL_TEMPLATES } from "@/components/terminal/terminal-templates";
import { cn } from "@/lib/cn";
import type { SessionSummary } from "@/lib/terminal-api";

/** UI-DIRECTION sidebar: logo → Terminal / Research / Skills / Alerts groups
 *  in exact order, user card pinned bottom. Group headers 10px uppercase
 *  tracking-wide muted; active item = mint left-bar + soft bg. */

function GroupHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="px-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
      {children}
    </h3>
  );
}

function NavItem({
  label,
  active,
  soon,
  dot,
  onClick,
  testId,
}: {
  label: string;
  active?: boolean;
  soon?: boolean;
  dot?: string;
  onClick?: () => void;
  testId?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      aria-disabled={soon || undefined}
      title={soon ? "Coming soon" : undefined}
      onClick={soon ? undefined : onClick}
      className={cn(
        "group relative flex w-full items-center gap-2 rounded-lg py-1.5 pl-3 pr-2 text-left text-[12px] transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30 active:scale-[0.99]",
        active
          ? "bg-primary-dim/50 font-semibold text-text"
          : "text-muted hover:bg-surface-2/70 hover:text-text",
        soon && "cursor-default opacity-60",
      )}
    >
      {/* Active item: mint left-bar. */}
      <span
        aria-hidden="true"
        className={cn(
          "absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-primary transition-opacity",
          active ? "opacity-100" : "opacity-0",
        )}
      />
      {dot ? <span aria-hidden="true" className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dot)} /> : null}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {soon ? (
        <span className="font-mono text-[9px] uppercase tracking-wide text-muted-2">soon</span>
      ) : null}
    </button>
  );
}

export function TerminalSessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onTemplate,
  loading,
  onCollapse,
}: {
  sessions: SessionSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onTemplate: (question: string) => void;
  loading?: boolean;
  onCollapse?: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => s.question.toLowerCase().includes(q));
  }, [sessions, query]);

  return (
    <aside
      data-testid="terminal-session-sidebar"
      className="flex h-full min-h-0 w-full flex-col rounded-xl border border-border bg-surface"
    >
      {/* Logo */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-3">
        <span
          aria-hidden="true"
          className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary font-mono text-[12px] font-black text-bg shadow-glow"
        >
          Æ
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[13px] font-black tracking-tight text-text">
            Research Terminal
          </h1>
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-2">
            paper research only
          </p>
        </div>
        {onCollapse ? (
          <button
            type="button"
            onClick={onCollapse}
            aria-label="Hide sidebar"
            className="rounded-md p-1 text-muted transition hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 active:scale-95"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path
                d="M9 3L5 7l4 4"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        ) : null}
      </div>

      <nav className="min-h-0 flex-1 space-y-4 overflow-y-auto p-2" aria-label="Terminal">
        {/* Terminal group */}
        <section className="space-y-1">
          <GroupHeader>Terminal</GroupHeader>
          <NavItem label="Research" active onClick={onNew} testId="terminal-new-session" />
          <NavItem label="Screener" soon />
          <NavItem label="Datasets" soon />
        </section>

        {/* Research group: search + recent sessions (truncated titles) */}
        <section className="space-y-1">
          <div className="flex items-center justify-between pr-1">
            <GroupHeader>Research</GroupHeader>
            <button
              type="button"
              onClick={onNew}
              aria-label="New research session"
              className="rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold text-primary transition hover:bg-primary-dim/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 active:scale-95"
            >
              + New
            </button>
          </div>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sessions…"
            aria-label="Search sessions"
            className="w-full rounded-lg border border-border bg-bg/55 px-2.5 py-1.5 text-[12px] text-text outline-none transition placeholder:text-muted-2 hover:border-border-light focus:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary/30"
          />
          <ul className="space-y-0.5">
            {loading ? (
              <li className="px-2 py-2 text-[11px] text-muted">Loading…</li>
            ) : filtered.length === 0 ? (
              <li className="px-2 py-2 text-[11px] text-muted">No saved sessions yet.</li>
            ) : (
              filtered.map((s) => (
                <li key={s.id}>
                  <NavItem
                    label={s.question}
                    active={s.id === activeId}
                    onClick={() => onSelect(s.id)}
                  />
                </li>
              ))
            )}
          </ul>
        </section>

        {/* Skills group: header links to the full /skills gallery */}
        <section className="space-y-1">
          <Link
            href="/skills"
            className="flex items-center gap-1 px-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2 transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
          >
            Skills
            <span aria-hidden="true" className="ml-auto">
              →
            </span>
          </Link>
          {TERMINAL_TEMPLATES.map((t) => (
            <NavItem
              key={t.id}
              label={t.name}
              dot={t.dot}
              onClick={() => onTemplate(t.question)}
            />
          ))}
        </section>

        {/* Alerts groups */}
        <section className="space-y-1">
          <GroupHeader>Personal Alerts</GroupHeader>
          <p className="px-2 py-1 text-[11px] text-muted-2">None yet — paper only.</p>
        </section>
        <section className="space-y-1">
          <GroupHeader>Subscribed Alerts</GroupHeader>
          <p className="px-2 py-1 text-[11px] text-muted-2">None yet — paper only.</p>
        </section>
      </nav>

      {/* User card pinned bottom */}
      <div className="mt-auto border-t border-border p-3">
        <div className="flex items-center gap-2.5 rounded-lg bg-surface-2/60 px-2.5 py-2">
          <span
            aria-hidden="true"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/15 font-mono text-[11px] font-black text-primary"
          >
            PT
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[12px] font-bold text-text">Paper Trader</p>
            <p className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wide text-muted-2">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
              simulated funds
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
