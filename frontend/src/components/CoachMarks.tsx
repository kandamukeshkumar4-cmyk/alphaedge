"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { NavIcon } from "@/components/nav-icons";
import { FEATURE_GROUPS, ALL_FEATURES } from "@/lib/feature-registry";

/*
 * Loop V62 (R3) — first-visit coach marks. A dismissable, non-blocking corner
 * card that spotlights the nav groups so a newcomer learns where everything
 * lives, then points at the full /features map.
 *
 * Storage: a single boolean "seen" flag in localStorage — NEVER auth data,
 * never anything but this flag. Non-modal (sits in the corner) so it does not
 * fight the first-bet onboarding modal. Entrance animation respects
 * prefers-reduced-motion.
 */

const SEEN_KEY = "alphaedge.coachmarks.v1";
const NEW_COUNT = ALL_FEATURES.filter((f) => f.badge === "NEW").length;

export function CoachMarks() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(SEEN_KEY)) setShow(true);
    } catch {
      // localStorage unavailable (SSR / private mode) — simply don't show.
    }
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(SEEN_KEY, "true");
    } catch {
      // ignore
    }
    // Plain unmount so dismissal is instant for everyone — including
    // prefers-reduced-motion users. Enter animation is CSS below, and the
    // global reduced-motion kill-switch (globals.css) zeroes it when required.
    setShow(false);
  }

  if (!show) return null;

  return (
    <aside
      aria-label="Getting started"
      className="fixed bottom-24 right-3 z-40 w-[min(92vw,340px)] animate-fade-up overflow-hidden rounded-2xl border border-primary/30 bg-surface shadow-lift lg:bottom-4 lg:right-4"
    >
          <div className="flex items-center justify-between gap-2 border-b border-border bg-surface-2/60 px-4 py-2.5">
            <p className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.12em] text-primary">
              <NavIcon name="compass" size={14} />
              Find your way around
            </p>
            <button
              type="button"
              onClick={dismiss}
              aria-label="Dismiss getting-started tips"
              className="grid h-6 w-6 place-items-center rounded-md text-muted-2 transition hover:bg-surface-3 hover:text-text"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
                <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className="px-4 py-3">
            <p className="text-[13px] leading-relaxed text-muted">
              Everything AlphaEdge does is grouped in the top nav. Here&rsquo;s the map:
            </p>
            <ul className="mt-2.5 flex flex-col gap-1.5">
              {FEATURE_GROUPS.map((group) => (
                <li key={group.id} className="flex items-start gap-2.5">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md border border-primary/20 bg-primary-dim/40 text-primary">
                    <NavIcon name={group.icon} size={13} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[12px] font-bold text-text">{group.title}</span>
                    <span className="block text-[11px] leading-snug text-muted-2">{group.blurb}</span>
                  </span>
                </li>
              ))}
            </ul>

            {NEW_COUNT > 0 ? (
              <p className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-2">
                <span className="rounded-full border border-accent/40 bg-accent/12 px-1.5 py-0.5 font-mono text-[9px] font-black uppercase tracking-[0.1em] text-accent">
                  New
                </span>
                {NEW_COUNT} recently shipped surface{NEW_COUNT > 1 ? "s" : ""} — look for the badge.
              </p>
            ) : null}

            <div className="mt-3.5 flex items-center gap-2">
              <Link
                href="/features"
                onClick={dismiss}
                className="inline-flex h-9 flex-1 items-center justify-center rounded-xl bg-primary px-3 text-[13px] font-bold text-bg shadow-glow transition duration-200 ease-swift hover:brightness-110"
              >
                Open the feature map →
              </Link>
              <button
                type="button"
                onClick={dismiss}
                className="h-9 rounded-xl border border-border px-3 text-[13px] font-semibold text-muted transition hover:border-border-light hover:text-text"
              >
                Got it
              </button>
            </div>
          </div>
    </aside>
  );
}
