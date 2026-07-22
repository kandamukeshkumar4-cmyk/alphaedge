"use client";

/**
 * Loop V79 (A8) — composer per UI-DIRECTION: rounded-2xl surface-2 shell with
 * a mint focus ring; chips row bottom-left inside (static "AlphaEdge AI" model
 * pill, "Data +" sense popover with checkboxes, "Skills" template chip);
 * circular mint send that morphs to a stop-square while streaming.
 * Enter sends; Shift+Enter newline. Input disables with a subtle pulse while
 * streaming. Research only — no execution path.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { listSkills, type Skill } from "@/lib/skills-api";
import { SENSE_CHIPS, type SenseId } from "@/lib/terminal-api";

type Popover = "data" | "skills" | null;

function ArrowIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <path
        d="M7.5 12V3M3.5 7l4-4 4 4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" rx="2" fill="currentColor" />
    </svg>
  );
}

const CHIP =
  "rounded-pill border border-border bg-bg/40 px-2.5 py-1 text-[11px] font-semibold text-muted transition hover:border-border-light hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 active:scale-95";

export function TerminalComposer({
  senses,
  onSensesChange,
  onAsk,
  isRunning,
  hasSession,
  disabled,
  onRunSkill,
}: {
  senses: SenseId[];
  onSensesChange: (next: SenseId[]) => void;
  onAsk: (question: string, senses: SenseId[]) => Promise<void>;
  isRunning: boolean;
  /** Placeholder switches: follow-up in a session, describe-when-new. */
  hasSession?: boolean;
  disabled?: boolean;
  /** Run a skill from the Skills popover — opens its terminal session. */
  onRunSkill?: (skillId: string) => Promise<void> | void;
}) {
  const [value, setValue] = useState("");
  const [popover, setPopover] = useState<Popover>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillRunning, setSkillRunning] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const senseSet = useMemo(() => new Set(senses), [senses]);

  // Top 5 skills for the Skills popover (live-first, mock fallback).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { skills: items } = await listSkills(null);
      if (!cancelled) setSkills(items.slice(0, 5));
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!popover) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setPopover(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPopover(null);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [popover]);

  function toggleSense(id: SenseId) {
    if (senseSet.has(id)) {
      onSensesChange(senses.filter((s) => s !== id));
    } else {
      onSensesChange([...senses, id]);
    }
  }

  const blocked = disabled || isRunning;
  const canSend = value.trim().length > 0 && !blocked;

  async function submit() {
    const text = value.trim();
    if (!text || blocked) return;
    setValue("");
    setPopover(null);
    await onAsk(text, senses);
  }

  async function runSkillFromPopover(skill: Skill) {
    if (!onRunSkill || skillRunning) return;
    setSkillRunning(skill.id);
    setPopover(null);
    try {
      await onRunSkill(skill.id);
    } finally {
      setSkillRunning(null);
    }
  }

  return (
    <div
      ref={rootRef}
      data-testid="terminal-composer"
      className={cn(
        "relative rounded-2xl border border-border bg-surface-2 transition",
        "focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/25",
      )}
    >
      <textarea
        ref={inputRef}
        rows={2}
        value={value}
        disabled={blocked}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void submit();
          }
        }}
        placeholder={
          hasSession ? "Ask a follow-up…" : "Describe what you want to research…"
        }
        aria-label="Research question"
        className={cn(
          "min-h-[56px] w-full resize-none bg-transparent px-4 pt-3.5 text-sm text-text outline-none",
          "placeholder:text-muted-2 disabled:animate-pulse disabled:opacity-60",
        )}
      />

      <div className="flex flex-wrap items-center gap-2 px-3 pb-3">
        {/* Model pill (static) */}
        <span className="rounded-pill border border-border bg-bg/40 px-2.5 py-1 text-[11px] font-semibold text-muted">
          AlphaEdge AI
        </span>

        {/* Data + — sense selector popover (checkboxes) */}
        <span className="relative">
          <button
            type="button"
            data-testid="terminal-sense-chips"
            aria-haspopup="true"
            aria-expanded={popover === "data"}
            onClick={() => setPopover((v) => (v === "data" ? null : "data"))}
            className={cn(CHIP, popover === "data" && "border-primary/40 text-primary")}
          >
            Data +
          </button>
          {popover === "data" ? (
            <div
              role="group"
              aria-label="Data senses"
              className="absolute bottom-full left-0 z-20 mb-2 w-44 rounded-xl border border-border bg-surface p-1.5 shadow-lift"
            >
              {SENSE_CHIPS.map((sense) => (
                <label
                  key={sense.id}
                  title={sense.blurb}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-text transition hover:bg-surface-2"
                >
                  <input
                    type="checkbox"
                    checked={senseSet.has(sense.id)}
                    onChange={() => toggleSense(sense.id)}
                    className="h-3.5 w-3.5 accent-primary"
                  />
                  <span>{sense.label}</span>
                </label>
              ))}
            </div>
          ) : null}
        </span>

        {/* Skills chip — top skills (skills-api), each runs a terminal session */}
        <span className="relative">
          <button
            type="button"
            data-testid="terminal-skills-chip"
            aria-haspopup="true"
            aria-expanded={popover === "skills"}
            onClick={() => setPopover((v) => (v === "skills" ? null : "skills"))}
            className={cn(CHIP, popover === "skills" && "border-primary/40 text-primary")}
          >
            Skills
          </button>
          {popover === "skills" ? (
            <div
              role="menu"
              aria-label="Skills gallery"
              className="absolute bottom-full left-0 z-20 mb-2 w-72 rounded-xl border border-border bg-surface p-1.5 shadow-lift"
            >
              {skills.length === 0 ? (
                <p className="px-2 py-2 text-[11px] text-muted">Loading skills…</p>
              ) : (
                skills.map((s) => (
                  <div
                    key={s.id}
                    role="menuitem"
                    className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-surface-2"
                  >
                    <span
                      aria-hidden="true"
                      className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary-dim/55 text-sm"
                    >
                      {s.icon}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12px] font-semibold text-text">
                        {s.name}
                      </span>
                      <span className="block truncate text-[11px] text-muted">
                        {s.description}
                      </span>
                    </span>
                    <button
                      type="button"
                      data-testid={`terminal-skill-run-${s.id}`}
                      disabled={!onRunSkill || skillRunning !== null}
                      onClick={() => void runSkillFromPopover(s)}
                      className={cn(
                        "ml-1 shrink-0 self-center rounded-md bg-primary px-2 py-1 text-[11px] font-bold text-bg transition",
                        "hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-95",
                        !onRunSkill || skillRunning !== null
                          ? "cursor-wait opacity-60"
                          : "",
                      )}
                    >
                      {skillRunning === s.id ? "…" : "Run"}
                    </button>
                  </div>
                ))
              )}
            </div>
          ) : null}
        </span>

        {/* Keep chip count stable for smoke even if popovers remount. */}
        <span className="sr-only">{SENSE_CHIPS.length} senses</span>

        {/* Send: circular mint arrow, morphs to stop-square while streaming.
            Empty/disabled → 40% opacity; streaming stop stays full mint. */}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!canSend}
          aria-label={isRunning ? "Streaming research" : "Send question"}
          className={cn(
            "ml-auto grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-bg shadow-glow transition",
            "hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-95",
            isRunning ? "disabled:opacity-100" : "disabled:opacity-40",
          )}
        >
          {isRunning ? <StopIcon /> : <ArrowIcon />}
        </button>
      </div>

      <p className="border-t border-border/70 px-4 py-1.5 font-mono text-[9px] uppercase tracking-wide text-muted-2">
        Analysis only · paper trading · no order submission
      </p>
    </div>
  );
}
