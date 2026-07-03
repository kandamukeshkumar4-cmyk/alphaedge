"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

const STORAGE_KEY = "ae_quest_onboarding_v1";

type Step = {
  icon: string;
  title: string;
  body: string;
  cta?: { label: string; href: string };
};

const STEPS: Step[] = [
  {
    icon: "◈",
    title: "Welcome to AlphaEdge",
    body: "A live prediction-market terminal mirroring Kalshi and Polymarket prices in real time — NBA, FIFA World Cup 2026, elections and more. Everything here runs on simulated funds: it's a paper-trading research platform, never real money.",
  },
  {
    icon: "⚡",
    title: "Live markets & signals",
    body: "Prices stream over WebSocket from both exchanges. A diff engine watches every tick for price jumps, order-book flips, whale position changes and unpriced news — and surfaces them in the Signals feed.",
    cta: { label: "See live signals", href: "/signals" },
  },
  {
    icon: "✦",
    title: "The AI analyst works for you",
    body: "When at least three independent signal layers align on one market, the AI analyst publishes a cited brief with a falsifiable claim. Every claim is graded against reality — accuracy and Brier scores are public.",
    cta: { label: "View track record", href: "/track-record" },
  },
  {
    icon: "▲",
    title: "Trade with a $100k paper bankroll",
    body: "Go long or short on any market with simulated funds. Orders run through the same risk-checked path as our agents. Climb the leaderboard, keep your streak, level up.",
    cta: { label: "Start trading", href: "/markets" },
  },
];

// First-visit onboarding flow (Questflow-style stepper). Dismiss persists.
export function QuestOnboarding() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {
      /* SSR / private mode */
    }
  }, []);

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "done");
    } catch {
      /* ignore */
    }
    setOpen(false);
  };

  if (!open) return null;
  const s = STEPS[step];
  const last = step === STEPS.length - 1;

  return (
    <div
      className="fixed inset-0 z-[70] grid place-items-center bg-black/70 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Welcome tour"
    >
      <div className="w-full max-w-md animate-fade-up rounded-2xl border border-border bg-surface p-6 shadow-lift">
        <div className="flex items-start justify-between">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-accent-dim text-2xl text-accent-bright">
            {s.icon}
          </span>
          <button
            type="button"
            onClick={dismiss}
            className="text-xs font-semibold text-muted-2 hover:text-text"
          >
            Skip
          </button>
        </div>
        <h2 className="mt-4 text-lg font-bold text-text">{s.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">{s.body}</p>
        {s.cta && (
          <Link
            href={s.cta.href}
            onClick={dismiss}
            className="mt-3 inline-block text-sm font-semibold text-accent-bright hover:underline"
          >
            {s.cta.label} →
          </Link>
        )}

        <div className="mt-6 flex items-center justify-between">
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  i === step ? "w-6 bg-accent-bright" : "w-1.5 bg-surface-3",
                )}
              />
            ))}
          </div>
          <div className="flex gap-2">
            {step > 0 && (
              <button
                type="button"
                onClick={() => setStep((v) => v - 1)}
                className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-muted hover:text-text"
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={() => (last ? dismiss() : setStep((v) => v + 1))}
              className="rounded-lg bg-accent-bright px-4 py-2 text-sm font-semibold text-bg transition hover:bg-accent"
            >
              {last ? "Let's go" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
