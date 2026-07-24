"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

import { markOnboarded } from "@/lib/onboarding";

type TourStep = {
  key: string;
  label: string;
  description: string;
  href: string;
  tone: "primary" | "secondary" | "gold";
  glyph: "terminal" | "skills" | "scanners" | "screener";
};

const TOUR_STEPS: TourStep[] = [
  {
    key: "terminal",
    label: "Terminal",
    description: "Ask the AI to investigate a market and turn scattered signals into a research trail.",
    href: "/terminal",
    tone: "primary",
    glyph: "terminal",
  },
  {
    key: "skills",
    label: "Skills",
    description: "Run one-click research workflows when you want a focused answer without starting from scratch.",
    href: "/skills",
    tone: "secondary",
    glyph: "skills",
  },
  {
    key: "scanners",
    label: "Scanners",
    description: "Set up 24/7 alerts that watch paper markets for the conditions you care about.",
    href: "/scanners",
    tone: "gold",
    glyph: "scanners",
  },
  {
    key: "screener",
    label: "Screener",
    description: "Scan the market board for edges, then decide what deserves a closer look.",
    href: "/screener",
    tone: "primary",
    glyph: "screener",
  },
];

const TOTAL_PANELS = TOUR_STEPS.length + 1;

export function OnboardingTour({ onComplete }: { onComplete?: () => void }) {
  const [panel, setPanel] = useState(0);
  const dialogRef = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion() ?? false;
  const currentStep = panel > 0 ? TOUR_STEPS[panel - 1] : null;

  const complete = useCallback(() => {
    markOnboarded();
    onComplete?.();
  }, [onComplete]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        complete();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    dialogRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [complete]);

  useEffect(() => {
    dialogRef.current?.focus();
  }, [panel]);

  function next() {
    if (panel === TOTAL_PANELS - 1) {
      complete();
      return;
    }
    setPanel((value) => value + 1);
  }

  const transition = reduceMotion
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 260, damping: 28, mass: 0.7 };

  return (
    <section
      aria-label="AlphaEdge onboarding"
      className="fixed inset-0 z-[100] grid place-items-center p-4 sm:p-6"
      data-testid="onboarding-overlay"
    >
      <button
        type="button"
        aria-label="Close onboarding tour"
        className="absolute inset-0 cursor-default bg-bg/85 backdrop-blur-sm"
        onClick={complete}
      />

      <motion.article
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        tabIndex={-1}
        initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={transition}
        className="relative flex min-h-96 w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-primary/25 bg-surface shadow-lift focus:outline-none"
        data-testid="onboarding-tour"
      >
        <header className="flex items-center justify-between border-b border-border bg-surface-2/55 px-5 py-4 sm:px-6">
          <p className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
            <span aria-hidden className="grid h-5 w-5 place-items-center rounded-md bg-primary-dim text-primary">
              <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-glow" />
            </span>
            AlphaEdge / orientation
          </p>
          <button
            type="button"
            onClick={complete}
            className="grid h-8 w-8 place-items-center rounded-lg text-muted transition hover:bg-surface-3 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            aria-label="Close onboarding tour"
          >
            <CloseIcon />
          </button>
        </header>

        <section className="flex flex-1 flex-col px-5 py-7 sm:px-8 sm:py-8">
          <nav aria-label="Onboarding progress" className="mb-8 flex items-center gap-2">
            {Array.from({ length: TOTAL_PANELS }, (_, index) => (
              <span
                key={index}
                aria-current={index === panel ? "step" : undefined}
                className={
                  index === panel
                    ? "h-1.5 w-8 rounded-pill bg-primary shadow-glow transition-all duration-250"
                    : "h-1.5 w-1.5 rounded-full bg-border transition-all duration-250"
                }
              />
            ))}
            <span className="ml-auto font-mono text-[10px] tabular-nums text-muted-2">
              {String(panel + 1).padStart(2, "0")} / {String(TOTAL_PANELS).padStart(2, "0")}
            </span>
          </nav>

          <AnimatePresence mode="wait" initial={false}>
            <motion.section
              key={currentStep?.key ?? "welcome"}
              initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -4 }}
              transition={transition}
              className="flex flex-1 flex-col"
            >
              {currentStep ? <StepPanel step={currentStep} /> : <WelcomePanel />}
            </motion.section>
          </AnimatePresence>

          <footer className="mt-8 flex items-center justify-between gap-3 border-t border-border pt-5">
            <button
              type="button"
              onClick={complete}
              className="rounded-lg px-2 py-2 text-xs font-semibold text-muted transition hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              Skip
            </button>
            <span className="flex items-center gap-2">
              {panel > 0 ? (
                <button
                  type="button"
                  onClick={() => setPanel((value) => Math.max(0, value - 1))}
                  className="rounded-lg border border-border px-3.5 py-2 text-xs font-semibold text-muted transition hover:border-border-light hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                >
                  Back
                </button>
              ) : null}
              <button
                type="button"
                onClick={next}
                className="rounded-lg bg-primary px-4 py-2 text-xs font-bold text-bg shadow-glow transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 active:scale-[0.98]"
              >
                {panel === TOTAL_PANELS - 1 ? "Finish" : "Next"}
                <span aria-hidden className="ml-2">→</span>
              </button>
            </span>
          </footer>
        </section>
      </motion.article>
    </section>
  );
}

function WelcomePanel() {
  return (
    <section>
      <p className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-primary">
        A calmer way to find the edge
      </p>
      <h1 id="onboarding-title" className="mt-3 max-w-md text-3xl font-black leading-tight tracking-[-0.03em] text-text sm:text-4xl">
        Research first. Trade with a reason.
      </h1>
      <p className="mt-5 max-w-md text-sm leading-relaxed text-muted">
        AlphaEdge — AI research desk for paper prediction-market trading. Simulated funds only.
      </p>
      <section className="mt-8 grid grid-cols-3 gap-2" aria-label="AlphaEdge principles">
        <Principle label="Ask" value="AI-led" />
        <Principle label="Check" value="Evidence" />
        <Principle label="Act" value="Paper only" />
      </section>
    </section>
  );
}

function StepPanel({ step }: { step: TourStep }) {
  const toneClasses = {
    primary: "border-primary/35 bg-primary-dim/35 text-primary",
    secondary: "border-secondary/35 bg-secondary-dim/45 text-secondary",
    gold: "border-gold/35 bg-gold/10 text-gold",
  } as const;

  return (
    <section>
      <p className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-muted-2">
        Core surface / {step.key}
      </p>
      <span className={`mt-6 grid h-14 w-14 place-items-center rounded-2xl border ${toneClasses[step.tone]}`}>
        <FeatureIcon glyph={step.glyph} />
      </span>
      <h1 id="onboarding-title" className="mt-5 text-3xl font-black tracking-[-0.03em] text-text">
        {step.label}
      </h1>
      <p className="mt-4 max-w-md text-base leading-relaxed text-muted">{step.description}</p>
      <a
        href={step.href}
        className="mt-7 inline-flex w-fit items-center gap-2 rounded-pill border border-border bg-bg/45 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted transition hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        Open {step.label}
        <span aria-hidden>↗</span>
      </a>
    </section>
  );
}

function Principle({ label, value }: { label: string; value: string }) {
  return (
    <section className="rounded-xl border border-border bg-bg/35 px-3 py-3">
      <p className="font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-muted-2">{label}</p>
      <p className="mt-1 text-xs font-bold text-text">{value}</p>
    </section>
  );
}

function FeatureIcon({ glyph }: { glyph: TourStep["glyph"] }) {
  if (glyph === "terminal") {
    return <span aria-hidden className="font-mono text-xl font-bold">&gt;_</span>;
  }

  if (glyph === "skills") {
    return <span aria-hidden className="font-mono text-lg font-bold">✦</span>;
  }

  if (glyph === "scanners") {
    return <span aria-hidden className="h-5 w-5 rounded-full border-2 border-current" />;
  }

  return <span aria-hidden className="grid grid-cols-2 gap-1"><span className="h-2 w-2 rounded-sm bg-current" /><span className="h-2 w-2 rounded-sm bg-current" /><span className="h-2 w-2 rounded-sm bg-current" /><span className="h-2 w-2 rounded-sm bg-current" /></span>;
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 fill-none stroke-current" strokeWidth="1.8">
      <path d="m5 5 10 10M15 5 5 15" strokeLinecap="round" />
    </svg>
  );
}
