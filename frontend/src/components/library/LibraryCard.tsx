"use client";

/**
 * Loop V85 (L3) — unified library card. Adapts a skill OR a scanner into one
 * card shape for the /library hub, reusing the skills/scanner visual language
 * (mint-on-charcoal tokens, t-rise + t-stagger-* entrance, mono meta chips).
 * Action row: Run (skill) / View (scanner) + Subscribe toggle + Fork button.
 *
 * The card is presentational — fork/subscribe/run side effects are delegated
 * to the hub via callbacks so the hub owns data + toast feedback. Paper only.
 */

import Link from "next/link";

import { cn } from "@/lib/cn";

export type LibraryEntryKind = "skill" | "scanner";

export type LibraryEntry = {
  kind: LibraryEntryKind;
  id: string;
  name: string;
  description: string;
  icon: string;
  /** "128 runs" (skill) / "every 15 min · active" (scanner). */
  meta: string;
  /** "private" pill when the entry is not public. */
  private?: boolean;
  /** Where the View/Run primary action lands. */
  href: string;
};

function staggerClass(index: number): string {
  if (index >= 5) return "";
  return `t-stagger-${Math.min(index + 1, 4)}`;
}

export function LibraryCard({
  entry,
  index,
  subscribed,
  busy,
  forkBusy,
  onToggleSubscribe,
  onFork,
  onRun,
}: {
  entry: LibraryEntry;
  index: number;
  subscribed: boolean;
  busy: boolean;
  forkBusy: boolean;
  onToggleSubscribe: (entry: LibraryEntry) => void;
  onFork: (entry: LibraryEntry) => void;
  onRun: (entry: LibraryEntry) => void;
}) {
  const isSkill = entry.kind === "skill";
  return (
    <li
      data-testid="library-card"
      data-kind={entry.kind}
      className={cn(
        "t-rise group relative flex flex-col rounded-2xl border border-border bg-surface p-4 transition",
        "hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-2/60 hover:shadow-lift",
        "focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/25",
        staggerClass(index),
      )}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-dim/55 text-xl"
        >
          {entry.icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="rounded border border-border bg-bg/40 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-muted-2">
              {entry.kind}
            </span>
            {entry.private ? (
              <span className="rounded border border-border bg-bg/40 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-muted-2">
                private
              </span>
            ) : null}
          </div>
          <h3 className="mt-1 truncate text-[15px] font-bold tracking-tight text-text">
            {entry.name}
          </h3>
          <p className="mt-0.5 line-clamp-2 text-[12px] leading-relaxed text-muted">
            {entry.description}
          </p>
        </div>
      </div>

      <p className="mt-3 font-mono text-[10px] uppercase tracking-wide text-muted-2">
        {entry.meta}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-border/60 pt-3">
        {isSkill ? (
          <button
            type="button"
            data-testid="library-run"
            onClick={() => onRun(entry)}
            disabled={busy}
            aria-label={`Run ${entry.name}`}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-bold text-bg shadow-glow transition",
              "hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-95",
              busy ? "cursor-wait opacity-70" : "disabled:opacity-40",
            )}
          >
            {busy ? "Running…" : "Run"}
          </button>
        ) : (
          <Link
            href={entry.href}
            data-testid="library-view"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-bold text-bg shadow-glow transition hover:brightness-110 active:scale-95"
          >
            View
          </Link>
        )}

        <button
          type="button"
          data-testid="library-subscribe"
          onClick={() => onToggleSubscribe(entry)}
          aria-pressed={subscribed}
          aria-label={subscribed ? `Unsubscribe from ${entry.name}` : `Subscribe to ${entry.name}`}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] font-bold transition active:scale-95",
            subscribed
              ? "border-primary/50 bg-primary-dim/55 text-primary"
              : "border-border text-muted hover:border-border-light hover:text-text",
          )}
        >
          <BellIcon filled={subscribed} />
          {subscribed ? "Subscribed" : "Subscribe"}
        </button>

        <button
          type="button"
          data-testid="library-fork"
          onClick={() => onFork(entry)}
          disabled={forkBusy}
          aria-label={`Fork ${entry.name} into your library`}
          title="Fork a copy into your library"
          className={cn(
            "ml-auto inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-[12px] font-bold text-muted transition active:scale-95",
            "hover:border-primary/40 hover:text-primary disabled:cursor-wait disabled:opacity-60",
          )}
        >
          <ForkIcon />
          {forkBusy ? "Forking…" : "Fork"}
        </button>
      </div>
    </li>
  );
}

function BellIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} aria-hidden>
      <path
        d="M6 8a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6zM10 20a2 2 0 0 0 4 0"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ForkIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M7 4v6a3 3 0 0 0 3 3h4a3 3 0 0 0 3-3V4M12 13v7M9 20h6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
