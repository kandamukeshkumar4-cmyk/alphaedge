import Link from "next/link";
import type { ReactNode } from "react";

import { NavIcon, type NavIconKey } from "@/components/nav-icons";
import { cn } from "@/lib/cn";

/*
 * Loop V62 (R3) — the canonical honest empty state. Every dead-end should say
 * what will appear here and link to the feature that feeds it, so an empty
 * surface is a signpost, not a wall. API matches the ad-hoc per-page
 * EmptyStates (title/body/cta) so those can migrate to this over time.
 *
 * Honesty guardrail: `body` describes what will appear — never a fabricated
 * number or a promise. `cta` points at the real feeder route.
 */
export function EmptyState({
  title,
  body,
  cta,
  icon,
  className,
}: {
  title: string;
  body: ReactNode;
  /** The feature that feeds this surface — where the user goes to fill it. */
  cta?: { href: string; label: string };
  icon?: NavIconKey;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-2xl border border-border bg-surface px-6 py-10 text-center",
        className,
      )}
    >
      {icon ? (
        <span className="mb-3 grid h-11 w-11 place-items-center rounded-xl border border-border bg-surface-2 text-muted-2">
          <NavIcon name={icon} size={20} />
        </span>
      ) : null}
      <p className="text-base font-black tracking-tight text-text">{title}</p>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">{body}</p>
      {cta ? (
        <Link
          href={cta.href}
          className="mt-4 inline-flex h-9 items-center rounded-xl bg-primary px-4 text-sm font-bold text-bg shadow-glow transition duration-200 hover:brightness-110"
        >
          {cta.label} →
        </Link>
      ) : null}
    </div>
  );
}
