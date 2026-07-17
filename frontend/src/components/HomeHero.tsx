"use client";

import Link from "next/link";

import { MotionReveal } from "@/components/MotionReveal";
import { NavIcon, type NavIconKey } from "@/components/nav-icons";
import { cn } from "@/lib/cn";

/*
 * Loop V62 (R2) — home comprehension hero. The 15-second rule lives here: a
 * first-time visitor must learn what AlphaEdge is and see the three core loops
 * before scrolling. Honest paper-trading copy up top (simulated funds, no
 * real-money execution); the loops Predict -> Track -> Prove are animated cards
 * that deep-link to /markets, /pods and /eval. Scroll-reveal reuses the shared
 * MotionReveal pattern, which already respects prefers-reduced-motion.
 */

type Loop = {
  step: string;
  name: string;
  icon: NavIconKey;
  blurb: string;
  href: string;
  cta: string;
};

const LOOPS: Loop[] = [
  {
    step: "01",
    name: "Predict",
    icon: "intel",
    blurb: "Forecast any market. Each one shows the model's probability right next to the market price, so the edge is obvious.",
    href: "/markets",
    cta: "Browse markets",
  },
  {
    step: "02",
    name: "Track",
    icon: "trade",
    blurb: "Track the calls. A fleet of paper pods trades the signal live — equity curves, decisions and telemetry, no real money.",
    href: "/pods",
    cta: "Open the pod fleet",
  },
  {
    step: "03",
    name: "Prove",
    icon: "proof",
    blurb: "Prove the edge. Every call is graded against the real outcome — calibration, drift and closing-line value.",
    href: "/eval",
    cta: "See the proof",
  },
];

export function HomeHero() {
  return (
    <section
      aria-labelledby="home-hero-title"
      className="relative overflow-hidden rounded-2xl border border-border bg-surface"
      style={{
        backgroundImage:
          "radial-gradient(80% 130% at 10% 0%, rgba(0,232,176,0.10) 0%, transparent 55%), radial-gradient(70% 120% at 100% 100%, rgba(45,212,191,0.08) 0%, transparent 60%)",
      }}
    >
      <div className="px-5 py-6 sm:px-8 sm:py-8">
        <MotionReveal>
          <p className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.14em] text-primary">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.8)]" />
            Paper-trading prediction markets
          </p>
          <h1
            id="home-hero-title"
            className="mt-2 max-w-2xl text-2xl font-black leading-[1.05] tracking-tight text-text sm:text-[34px]"
          >
            See the edge, trade it on paper, and prove the call.
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
            AlphaEdge is a <span className="font-semibold text-text">paper-trading simulation</span>{" "}
            for sports and election markets — simulated funds only, with no real-money execution.
            Forecast a market, let the paper pods trade the signal, and watch the model get graded
            against real outcomes.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Link
              href="/markets"
              className="rounded-lg bg-primary px-4 py-2 text-[13px] font-bold text-bg shadow-glow transition duration-200 hover:brightness-110"
            >
              Explore markets
            </Link>
            <Link
              href="/features"
              className="rounded-lg border border-border-light bg-bg/35 px-4 py-2 text-[13px] font-semibold text-text transition duration-200 hover:border-primary hover:text-primary"
            >
              See everything it does
            </Link>
          </div>
        </MotionReveal>

        <ol className="mt-6 grid gap-3 sm:grid-cols-3">
          {LOOPS.map((loop, i) => (
            <MotionReveal key={loop.name} delay={0.08 + i * 0.08} className="h-full">
              <li className="h-full list-none">
                <Link
                  href={loop.href}
                  className={cn(
                    "group flex h-full flex-col rounded-xl border border-border bg-bg/40 p-4 transition duration-200 ease-swift",
                    "hover:-translate-y-0.5 hover:border-primary/45 hover:shadow-glow",
                    "focus-visible:border-primary/45 motion-reduce:transform-none motion-reduce:transition-none",
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-primary/25 bg-primary-dim/40 text-primary">
                      <NavIcon name={loop.icon} size={18} />
                    </span>
                    <span className="font-mono text-[11px] font-bold tracking-[0.14em] text-muted-2">
                      {loop.step}
                    </span>
                    <span className="text-sm font-black tracking-tight text-text group-hover:text-primary">
                      {loop.name}
                    </span>
                  </div>
                  <p className="mt-2.5 text-[13px] leading-relaxed text-muted">{loop.blurb}</p>
                  <span className="mt-auto pt-3 text-[12px] font-bold text-muted-2 transition group-hover:text-primary">
                    {loop.cta} →
                  </span>
                </Link>
              </li>
            </MotionReveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
