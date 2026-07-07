import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/*
 * QuestFlow design kit — shared page primitives so every tab reads as one
 * product. All styling flows through the central Tailwind tokens
 * (bg/surface/border/primary/accent/secondary/muted); see
 * docs/QUESTFLOW_DESIGN_SYSTEM.md. Retune tokens, not these components.
 */

export function PageShell({
  children,
  width = "wide",
  className,
}: {
  children: ReactNode;
  width?: "narrow" | "medium" | "wide";
  className?: string;
}) {
  const max =
    width === "narrow" ? "max-w-[960px]" : width === "medium" ? "max-w-[1200px]" : "max-w-[1440px]";
  return (
    <main className={cn("mx-auto px-4 py-6 sm:px-5 sm:py-8", max, className)}>{children}</main>
  );
}

export function PageHeader({
  kicker,
  title,
  subtitle,
  actions,
}: {
  kicker?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {kicker ? (
          <p className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.14em] text-primary">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.8)]" />
            {kicker}
          </p>
        ) : null}
        <h1 className="mt-2 text-2xl font-black tracking-tight text-text sm:text-3xl">{title}</h1>
        {subtitle ? <p className="mt-2 max-w-2xl text-sm text-muted">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function SectionHeader({
  title,
  action,
  className,
}: {
  title: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-end justify-between gap-3", className)}>
      <h2 className="text-base font-black tracking-tight text-text sm:text-lg">{title}</h2>
      {action}
    </div>
  );
}

export function Panel({
  children,
  className,
  title,
  action,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  action?: ReactNode;
  padded?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-border bg-surface shadow-card",
        className,
      )}
    >
      {title ? (
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <h3 className="text-sm font-black tracking-tight text-text">{title}</h3>
          {action}
        </div>
      ) : null}
      <div className={cn(padded && "p-4 sm:p-5")}>{children}</div>
    </section>
  );
}

type Tone = "neutral" | "up" | "down" | "accent";

const DELTA_TONE: Record<Tone, string> = {
  neutral: "text-muted",
  up: "text-primary",
  down: "text-danger",
  accent: "text-accent",
};

export function StatTile({
  label,
  value,
  delta,
  deltaTone = "neutral",
  hint,
  accent,
}: {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  deltaTone?: Tone;
  hint?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-surface-2/60 px-3.5 py-3",
        accent ? "border-primary/30 bg-primary-dim/40" : "border-border",
      )}
    >
      <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted-2">{label}</div>
      <div className="mt-1 font-mono text-xl font-black tabular-nums text-text">{value}</div>
      {delta != null ? (
        <div className={cn("mt-0.5 font-mono text-xs font-bold tabular-nums", DELTA_TONE[deltaTone])}>
          {delta}
        </div>
      ) : null}
      {hint != null ? <div className="mt-0.5 text-[11px] text-muted-2">{hint}</div> : null}
    </div>
  );
}

export function StatRow({
  children,
  cols = 4,
  className,
}: {
  children: ReactNode;
  cols?: 2 | 3 | 4;
  className?: string;
}) {
  const grid =
    cols === 2 ? "grid-cols-2" : cols === 3 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 lg:grid-cols-4";
  return <div className={cn("grid gap-3", grid, className)}>{children}</div>;
}

export function AiEdge({
  label = "AI edge",
  value,
  className,
}: {
  label?: string;
  value: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent/12 px-2.5 py-1 font-mono text-[11px] font-black text-accent",
        className,
      )}
    >
      <SparkGlyph />
      {label} {value}
    </span>
  );
}

export type SegOption<T extends string> = { value: T; label: ReactNode };

export function SegTabs<T extends string>({
  value,
  onChange,
  options,
  size = "md",
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: SegOption<T>[];
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-xl border border-border bg-surface p-1",
        className,
      )}
      role="tablist"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded-lg font-bold transition",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm",
              active
                ? "bg-primary text-bg shadow-[0_0_16px_rgba(45,212,191,0.25)]"
                : "text-muted hover:bg-surface-2 hover:text-text",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function Chip({
  active,
  children,
  onClick,
}: {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "shrink-0 whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm font-bold transition",
        active
          ? "border-primary/50 bg-primary/12 text-primary"
          : "border-border bg-surface text-muted hover:border-border-light hover:text-text",
      )}
    >
      {children}
    </button>
  );
}

function SparkGlyph() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z" />
    </svg>
  );
}
