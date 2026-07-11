"use client";

// F05: 3-step first-bet guided flow on first visit — what a price means, what
// our edge/signals mean, then place a paper trade on a suggested liquid market.
// localStorage dismissal via the shared useOnboarding hook. Quest tokens.
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchMarkets } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { FIRST_BET_STEPS, pickSuggestedMarket } from "@/lib/onboarding-first-bet";
import type { Market } from "@/lib/mock-data";
import { useDialog } from "@/hooks/useDialog";
import { useOnboarding } from "@/hooks/useOnboarding";

export function FirstBetOnboarding() {
  const { shouldShow, markDone } = useOnboarding();
  const [step, setStep] = useState(0);
  const [suggested, setSuggested] = useState<Market | null>(null);
  const dialogRef = useDialog<HTMLDivElement>(markDone);

  useEffect(() => {
    if (!shouldShow) return;
    let dead = false;
    void fetchMarkets({ sort: "volume" }).then((markets) => {
      if (!dead) setSuggested(pickSuggestedMarket(markets));
    });
    return () => {
      dead = true;
    };
  }, [shouldShow]);

  if (!shouldShow) return null;

  const current = FIRST_BET_STEPS[step];
  const isLast = step === FIRST_BET_STEPS.length - 1;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)" }}
    >
      <div className="absolute inset-0 bg-black/60" onClick={markDone} aria-hidden="true" />

      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative z-10 w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-2xl focus:outline-none"
        role="dialog"
        aria-modal="true"
        aria-labelledby="first-bet-title"
      >
        <div className="mb-5 flex items-center gap-2">
          {FIRST_BET_STEPS.map((s, i) => (
            <div
              key={s.key}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors duration-300",
                i <= step ? "bg-primary" : "bg-surface-2",
              )}
            />
          ))}
        </div>

        <p className="text-[11px] font-black uppercase tracking-[0.14em] text-primary">
          Getting started · {step + 1} of {FIRST_BET_STEPS.length}
        </p>
        <h2 id="first-bet-title" className="mt-1 text-lg font-black text-text">
          {current.title}
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-muted">{current.body}</p>

        {isLast ? (
          <div className="mt-4 rounded-xl border border-border bg-surface-2 p-4">
            {suggested ? (
              <>
                <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted-2">
                  Suggested liquid market
                </p>
                <p className="mt-1 truncate text-sm font-bold text-text" title={suggested.title}>
                  {suggested.title}
                </p>
                <Link
                  href={`/trade?slug=${encodeURIComponent(suggested.slug)}`}
                  onClick={markDone}
                  className="mt-3 inline-flex h-9 items-center rounded-xl bg-primary px-4 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
                >
                  Place a paper trade →
                </Link>
              </>
            ) : (
              <>
                <p className="text-sm text-muted">
                  Browse the markets board to pick your first paper trade.
                </p>
                <Link
                  href="/markets"
                  onClick={markDone}
                  className="mt-3 inline-flex h-9 items-center rounded-xl bg-primary px-4 text-sm font-bold text-bg shadow-glow transition hover:brightness-110"
                >
                  Browse markets →
                </Link>
              </>
            )}
          </div>
        ) : null}

        <div className="mt-6 flex items-center justify-between gap-3">
          <button onClick={markDone} className="text-xs text-muted transition hover:text-text">
            Skip
          </button>
          {isLast ? (
            <button
              onClick={markDone}
              className="rounded-xl border border-border px-5 py-2 text-sm font-bold text-text transition hover:border-primary hover:text-primary"
            >
              Done
            </button>
          ) : (
            <button
              onClick={() => setStep((s) => Math.min(s + 1, FIRST_BET_STEPS.length - 1))}
              className="rounded-xl bg-primary px-5 py-2 text-sm font-bold text-bg transition hover:brightness-110 active:scale-95"
            >
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
