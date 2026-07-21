"use client";

import { cn } from "@/lib/cn";
import { SENSE_CHIPS, type SenseId } from "@/lib/terminal-api";

export function TerminalSenseChips({
  selected,
  onToggle,
  disabled,
}: {
  selected: ReadonlySet<SenseId>;
  onToggle: (id: SenseId) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="group"
      aria-label="Data senses"
      data-testid="terminal-sense-chips"
      className="flex flex-wrap gap-1.5"
    >
      {SENSE_CHIPS.map((sense) => {
        const on = selected.has(sense.id);
        return (
          <button
            key={sense.id}
            type="button"
            disabled={disabled}
            aria-pressed={on}
            title={sense.blurb}
            onClick={() => onToggle(sense.id)}
            className={cn(
              "rounded-md border px-2 py-1 text-[11px] font-semibold transition",
              on
                ? "border-primary/40 bg-primary-dim text-primary"
                : "border-border bg-bg/30 text-muted hover:border-border-light hover:text-text",
              disabled && "opacity-50",
            )}
          >
            {sense.label}
          </button>
        );
      })}
    </div>
  );
}
