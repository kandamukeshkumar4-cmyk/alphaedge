"use client";

import Link from "next/link";
import { useState } from "react";
import { cn } from "@/lib/cn";

const STEPS = ["Create account", "Confirm email", "Quick tutorial", "Claim $100k"];

export function OnboardingBanner() {
  const [dismissed, setDismissed] = useState(false);
  const current = 2; // step 2 of 4 in the demo
  if (dismissed) return null;

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-gradient-to-r from-surface to-surface-2 p-4">
      <button
        onClick={() => setDismissed(true)}
        className="absolute right-3 top-3 text-muted-2 transition hover:text-text"
        aria-label="Dismiss"
      >
        ✕
      </button>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-wider text-primary">
            Get ready to trade
          </div>
          <h2 className="mt-1 text-lg font-black text-text">
            Claim your $100,000 paper balance
          </h2>
          <p className="mt-0.5 text-sm text-muted">
            Step {current} of {STEPS.length} — {STEPS[current - 1]}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={cn(
                  "h-1.5 w-10 rounded-full transition",
                  i < current ? "bg-primary" : "bg-border-light",
                )}
              />
            ))}
          </div>
          <Link
            href="/auth/signup"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white transition hover:bg-accent"
          >
            Complete sign up
          </Link>
        </div>
      </div>
    </div>
  );
}
