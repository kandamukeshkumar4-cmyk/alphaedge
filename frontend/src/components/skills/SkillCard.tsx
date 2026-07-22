"use client";

/**
 * Loop V83 (S2) — one skill card. Xynth-library look on Astryx mint-on-charcoal
 * tokens: icon glyph, name, one-line description, step-count chip, run-count,
 * Run button. Hover lift; 40ms stagger entrance via t-rise + t-stagger-N
 * (zeroed by the reduced-motion kill-switch in globals.css). Paper only.
 */

import { cn } from "@/lib/cn";
import type { Skill } from "@/lib/skills-api";

function staggerClass(index: number): string {
  if (index >= 5) return "";
  // 40 / 80 / 120 / 160 ms — clamped to the 4 defined stagger steps.
  return `t-stagger-${Math.min(index + 1, 4)}`;
}

export function SkillCard({
  skill,
  index,
  onRun,
  busy,
}: {
  skill: Skill;
  index: number;
  onRun: (skill: Skill) => void;
  busy: boolean;
}) {
  const stepCount = skill.template.length;
  return (
    <li
      data-testid="skill-card"
      className={cn(
        "t-rise group relative flex flex-col rounded-2xl border border-border bg-surface p-4 transition",
        "hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-2/60 hover:shadow-lift",
        "focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/25",
        staggerClass(index),
      )}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-dim/55 text-xl"
        >
          {skill.icon}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[15px] font-bold tracking-tight text-text">
            {skill.name}
          </h3>
          <p className="mt-0.5 line-clamp-2 text-[12px] leading-relaxed text-muted">
            {skill.description}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {stepCount > 0 ? (
          <span className="rounded-pill border border-border bg-bg/40 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-muted">
            {stepCount} {stepCount === 1 ? "step" : "steps"}
          </span>
        ) : null}
        <span className="rounded-pill border border-border bg-bg/40 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-muted-2">
          {skill.run_count} {skill.run_count === 1 ? "run" : "runs"}
        </span>
        {!skill.is_public ? (
          <span className="rounded-pill border border-border bg-bg/40 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-muted-2">
            private
          </span>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between gap-2">
        <p className="font-mono text-[9px] uppercase tracking-wide text-muted-2">
          opens a research session
        </p>
        <button
          type="button"
          data-testid="skill-run"
          onClick={() => onRun(skill)}
          disabled={busy}
          aria-label={`Run ${skill.name} skill`}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-[12px] font-bold text-bg shadow-glow transition",
            "hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-95",
            busy ? "cursor-wait opacity-70" : "disabled:opacity-40",
          )}
        >
          {busy ? "Running…" : "Run"}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path
              d="M2.5 6h7M6.5 3l3 3-3 3"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </li>
  );
}
