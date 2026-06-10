"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";

type Step = 0 | 1 | 2;

const STEPS: { title: string; body: React.ReactNode }[] = [
  {
    title: "Welcome to AlphaEdge",
    body: (
      <div className="space-y-3 text-sm text-muted">
        <p>
          AlphaEdge is a <span className="text-text font-semibold">paper-trading</span> prediction
          market platform for sports, politics, crypto, and more.
        </p>
        <p>
          All markets use <span className="text-accent font-semibold">simulated funds only</span>{" "}
          — no real money, no payment rails.
        </p>
        <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
          ⚠️ PAPER_TRADING_ONLY — this is a research and portfolio demonstration platform.
        </p>
      </div>
    ),
  },
  {
    title: "How it works",
    body: (
      <ul className="space-y-3 text-sm text-muted">
        <li className="flex gap-3">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-dim text-xs font-bold text-primary">
            1
          </span>
          <span>
            Browse markets across sports, politics, crypto, culture, and economics.
          </span>
        </li>
        <li className="flex gap-3">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-dim text-xs font-bold text-primary">
            2
          </span>
          <span>
            Use AI forecasts and CLV signals to find edge — all provisional until CLV-validated.
          </span>
        </li>
        <li className="flex gap-3">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-dim text-xs font-bold text-primary">
            3
          </span>
          <span>
            Place paper orders, track your portfolio PnL, and climb the leaderboard.
          </span>
        </li>
      </ul>
    ),
  },
  {
    title: "Your paper balance",
    body: (
      <div className="space-y-3 text-sm text-muted">
        <div className="rounded-xl border border-border bg-surface-2 p-4 text-center">
          <p className="text-xs uppercase tracking-widest text-muted">Starting balance</p>
          <p className="mt-1 text-3xl font-black text-text">$100,000</p>
          <p className="mt-1 text-xs text-muted">Simulated funds</p>
        </div>
        <p>
          Your balance resets if you clear local data. Top up anytime from the portfolio page.
        </p>
        <p>
          Compete with other traders on the leaderboard — ranked by realized PnL from settled
          trades.
        </p>
      </div>
    ),
  },
];

type Props = {
  onDone: () => void;
};

export function OnboardingModal({ onDone }: Props) {
  const [step, setStep] = useState<Step>(0);

  function next() {
    if (step < 2) {
      setStep((s) => (s + 1) as Step);
    } else {
      onDone();
    }
  }

  function skip() {
    onDone();
  }

  const current = STEPS[step];
  const isLast = step === 2;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)" }}
    >
      <div
        className="absolute inset-0 bg-black/60"
        onClick={skip}
        aria-hidden="true"
      />

      <div
        className={cn(
          "relative z-10 w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-2xl",
          "transition-all duration-300",
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
      >
        {/* Step indicators */}
        <div className="mb-5 flex items-center gap-2">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors duration-300",
                i <= step ? "bg-primary" : "bg-surface-2",
              )}
            />
          ))}
        </div>

        <h2 id="onboarding-title" className="text-lg font-black text-text">
          {current.title}
        </h2>

        <div className="mt-4">{current.body}</div>

        <div className="mt-6 flex items-center justify-between gap-3">
          <button
            onClick={skip}
            className="text-xs text-muted transition hover:text-text"
          >
            Skip
          </button>
          <button
            onClick={next}
            className="rounded-xl bg-primary px-5 py-2 text-sm font-bold text-white transition hover:bg-primary/90 active:scale-95"
          >
            {isLast ? "Get started" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );
}
