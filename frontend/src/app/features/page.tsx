import type { Metadata } from "next";
import Link from "next/link";

import { MotionReveal } from "@/components/MotionReveal";
import { NavIcon } from "@/components/nav-icons";
import { PageHeader, PageShell } from "@/components/ui/kit";
import { FEATURE_GROUPS, type FeatureEntry } from "@/lib/feature-registry";
import { cn } from "@/lib/cn";

export const metadata: Metadata = {
  title: "Features — AlphaEdge",
  description:
    "The full map of everything AlphaEdge does: markets, AI analysis, proof dashboards, pods, social and more — every capability with a one-line description and a direct link.",
};

const SURFACE_LABEL: Record<NonNullable<FeatureEntry["surface"]>, string> = {
  page: "Page",
  overlay: "Overlay",
  embedded: "Embedded",
};

/**
 * Loop V62 (R1) — /features map page. Renders the whole capability inventory
 * from the single-source feature registry so a first-time visitor can see, in
 * one place, what AlphaEdge does and where every feature lives. Each card deep
 * links to the real surface; embedded/overlay features say where they live.
 */
export default function FeaturesPage() {
  const total = FEATURE_GROUPS.reduce((n, g) => n + g.features.length, 0);

  return (
    <PageShell width="wide">
      <PageHeader
        kicker="Everything AlphaEdge does"
        title="Feature map"
        subtitle={`All ${total} capabilities in one place — grouped, labeled, and one click away. AlphaEdge is a paper-trading simulation: every trade and balance is simulated, no real money is ever used.`}
      />

      <div className="flex flex-col gap-8">
        {FEATURE_GROUPS.map((group, gi) => (
          <MotionReveal key={group.id} delay={gi * 0.04}>
            <section aria-labelledby={`feature-group-${group.id}`}>
              <div className="mb-3 flex items-center gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-primary/25 bg-primary-dim/40 text-primary">
                  <NavIcon name={group.icon} size={18} />
                </span>
                <div className="min-w-0">
                  <h2
                    id={`feature-group-${group.id}`}
                    className="text-base font-black tracking-tight text-text sm:text-lg"
                  >
                    {group.title}
                  </h2>
                  <p className="text-xs text-muted-2">{group.blurb}</p>
                </div>
              </div>

              <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {group.features.map((feature) => (
                  <li key={feature.id}>
                    <FeatureCard feature={feature} />
                  </li>
                ))}
              </ul>
            </section>
          </MotionReveal>
        ))}
      </div>
    </PageShell>
  );
}

function FeatureCard({ feature }: { feature: FeatureEntry }) {
  const surface = feature.surface ?? "page";
  return (
    <Link
      href={feature.href}
      className={cn(
        "group flex h-full flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition",
        "hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-glow focus-visible:border-primary/40",
        "motion-reduce:transform-none motion-reduce:transition-none",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="truncate text-sm font-black tracking-tight text-text group-hover:text-primary">
          {feature.label}
        </h3>
        <div className="flex shrink-0 items-center gap-1.5">
          {feature.badge === "NEW" ? (
            <span className="rounded-full border border-accent/40 bg-accent/12 px-1.5 py-0.5 font-mono text-[9px] font-black uppercase tracking-[0.12em] text-accent">
              New
            </span>
          ) : null}
          {surface !== "page" ? (
            <span className="rounded-full border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.1em] text-muted-2">
              {SURFACE_LABEL[surface]}
            </span>
          ) : null}
          {feature.requiresAuth ? (
            <span
              title="Sign-in required"
              className="rounded-full border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-[0.1em] text-muted-2"
            >
              Auth
            </span>
          ) : null}
        </div>
      </div>

      <p className="mt-1.5 text-xs leading-relaxed text-muted">{feature.blurb}</p>
      {feature.note ? (
        <p className="mt-1.5 text-[11px] leading-relaxed text-muted-2">{feature.note}</p>
      ) : null}

      <span className="mt-auto pt-3 font-mono text-[11px] font-bold text-muted-2 transition group-hover:text-primary">
        {feature.href} →
      </span>
    </Link>
  );
}
